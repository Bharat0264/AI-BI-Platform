"""Real-browser regression checks against Flask and a mocked MongoDB database.

Install requirements-dev.txt and an Edge or Playwright Chromium browser to run.
Chart rendering is stubbed; analyst APIs and browser DOM interactions are real.
"""
import importlib
import os
from pathlib import Path
from threading import Thread

import mongomock
import pandas as pd
import pytest
from werkzeug.serving import make_server

pw = pytest.importorskip("playwright.sync_api")
from persistence.mongo import _set_test_client, ensure_indexes
from persistence.repositories import AuraRepository


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as runtime:
        channel = os.getenv("AURA_UI_BROWSER_CHANNEL", "msedge" if os.name == "nt" else "chromium")
        try:
            instance = runtime.chromium.launch(headless=True, channel=channel)
        except pw.Error as error:
            pytest.skip(f"UI browser unavailable; install Edge or run playwright install chromium: {error}")
        yield instance
        instance.close()


@pytest.fixture
def ui(monkeypatch, browser, tmp_path):
    client = mongomock.MongoClient()
    _set_test_client(client, "analyst_ui_test")
    ensure_indexes()
    server = importlib.import_module("server")
    store = AuraRepository(client.analyst_ui_test)
    data = pd.DataFrame({"Gross Sales": [100, 200, 300, 400], "Net Sales": [90, 150, 250, 300],
                         "Region": ["North", "South", "North", "South"], "Category": ["Office"] * 4})
    current = {"frame": data, "workspace": "UI Workspace", "real_financial_gate": server.financial_dashboard_available,
               "real_analysis_payload": server.analysis_payload, "real_dataset_from_request": server.dataset_from_request}
    def context(frame, source):
        workspace = store.workspace(current["workspace"])
        return workspace, store.dataset(workspace, source, frame, "data/sales.csv")
    monkeypatch.setattr(server, "PERSISTENCE", store)
    monkeypatch.setattr(server, "aura_context", context)
    monkeypatch.setattr(server, "dataset_from_request", lambda: (current["frame"].copy(), "sales.csv"))
    monkeypatch.setattr(server, "get_setting", lambda key, default=None: {"name": "UI Analyst", "workspace": current["workspace"]} if key == "current_user" else default)
    monkeypatch.setattr(server.GeminiEvidenceProvider, "explain", lambda *args: None)
    def analysis(frame, source):
        payload = server.empty_payload()
        payload.update(source=source, rows=len(frame))
        return payload, 200
    monkeypatch.setattr(server, "analysis_payload", analysis)
    monkeypatch.setattr(server, "financial_dashboard_available", lambda frame: True)
    monkeypatch.setattr(server, "prepare_dataset", lambda frame: frame)
    monkeypatch.setattr(server, "predict_sales", lambda frame: (None, pd.DataFrame()))
    monkeypatch.setattr(server, "kpis", lambda frame: [])
    monkeypatch.setattr(server, "executive_summary", lambda frame: [])
    monkeypatch.setattr(server, "recommendations", lambda frame: [])
    monkeypatch.setattr(server, "anomalies", lambda frame: [])
    def report(*args, **kwargs):
        path = tmp_path / f"report-{store.db.reports.count_documents({})}.pdf"
        path.write_bytes(b"%PDF-1.4\nUI test placeholder")
        return str(path)
    monkeypatch.setattr(server, "generate_pdf_report", report)
    http = make_server("127.0.0.1", 0, server.app, threaded=True)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    browser_context = browser.new_context(viewport={"width": 1440, "height": 1050}, accept_downloads=True, reduced_motion="reduce")
    page = browser_context.new_page()
    page.route("https://cdn.plot.ly/**", lambda route: route.fulfill(content_type="application/javascript", body="window.Plotly={newPlot:()=>Promise.resolve(),Plots:{resize:()=>{}}};"))
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"http://127.0.0.1:{http.server_port}/#assistant")
    pw.expect(page.locator("#definitionScope")).to_contain_text("sales.csv")
    page.locator("#savedMeanings").evaluate("element => element.open = true")
    yield page, store, context(data, "sales.csv"), current, errors
    browser_context.close()
    http.shutdown()
    thread.join(timeout=5)


def ask(page, question="What is sales?"):
    page.locator("#question").fill(question)
    page.locator("#askButton").click()
    pw.expect(page.locator("#askButton")).to_be_enabled()


def capture(page, name, locator="#assistant"):
    target = os.getenv("AURA_UI_CAPTURE_DIR")
    if target:
        Path(target).mkdir(parents=True, exist_ok=True)
        page.locator(locator).screenshot(path=str(Path(target) / name))


def test_choose_once_remember_update_and_reviewed_recalculation(ui):
    page, store, (workspace, dataset), _, errors = ui
    ask(page)
    pw.expect(page.locator("#interpretationChoices .analyst-card")).to_have_count(2)
    capture(page, "phase-5-choices.png")
    page.locator('[data-action="choose"][data-index="1"]').click()
    pw.expect(page.locator("#answer")).to_contain_text("790.00")
    assert store.definition_defaults(workspace, dataset) == {}
    ask(page)
    page.locator('[data-action="remember"][data-index="1"]').click()
    pw.expect(page.locator("#definitionConfirmation")).to_be_visible()
    assert store.definition_defaults(workspace, dataset) == {}
    page.locator("#cancelDefinition").click()
    assert store.definition_defaults(workspace, dataset) == {}
    page.locator('[data-action="remember"][data-index="1"]').click()
    page.locator("#confirmDefinition").click()
    pw.expect(page.locator("#savedDefinitions")).to_contain_text("sales → Net Sales")
    ask(page)
    pw.expect(page.locator("#answer")).to_contain_text("saved definition sales, version 1")
    qid = store.db.ai_queries.find_one({"definition.selection": "saved definition"})["query_id"]
    page.locator("#definitionColumn").select_option("Gross Sales")
    page.locator("#reviewDefinition").click()
    page.locator("#confirmDefinition").click()
    pw.expect(page.locator("#savedDefinitions")).to_contain_text("sales → Gross Sales")
    pw.expect(page.locator("#answerFreshness")).to_contain_text("Needs updating")
    page.locator(f'[data-action="preview"][data-id="{qid}"]').click()
    pw.expect(page.locator("#recomputeOriginal")).to_contain_text("790.00")
    pw.expect(page.locator("#recomputePreview")).to_contain_text("1,000.00")
    count = store.db.ai_queries.count_documents({})
    capture(page, "phase-5-recalculation.png", "#recomputeReview")
    page.locator("#confirmRecompute").click()
    pw.expect(page.locator("#analystStatus")).to_contain_text("New answer saved")
    assert store.db.ai_queries.count_documents({}) == count + 1
    assert "790.00" in store._artifact(workspace, "answer", qid)["response"]
    page.locator("#viewDefinitionHistory").click()
    pw.expect(page.locator("#definitionHistory")).to_contain_text("Version 2")
    page.locator("#reviewDisable").click()
    page.locator("#confirmDefinition").click()
    pw.expect(page.locator("#savedDefinitions")).to_contain_text("No saved defaults")
    ask(page)
    pw.expect(page.locator("#interpretationChoices .analyst-card")).to_have_count(2)
    assert errors == []


def test_conflicting_confirmation_requires_new_review(ui):
    page, store, (workspace, dataset), _, errors = ui
    page.locator("#definitionColumn").select_option("Net Sales")
    page.locator("#reviewDefinition").click()
    pw.expect(page.locator("#definitionConfirmation")).to_be_visible()
    store.save_definition(workspace, dataset, "sales", "Gross Sales", "revenue", 0, "Other analyst")
    page.locator("#confirmDefinition").click()
    pw.expect(page.locator("#analystStatus")).to_contain_text("definition changed")
    pw.expect(page.locator("#definitionConfirmation")).to_be_hidden()
    assert store.definition_defaults(workspace, dataset)["sales"]["measure_column"] == "Gross Sales"
    assert errors == []


def test_workspace_change_cannot_commit_review_for_old_scope(ui):
    page, store, (workspace, dataset), current, errors = ui
    page.locator("#definitionColumn").select_option("Net Sales")
    page.locator("#reviewDefinition").click()
    pw.expect(page.locator("#definitionConfirmation")).to_be_visible()
    current["workspace"] = "Another workspace"
    page.locator("#confirmDefinition").click()
    pw.expect(page.locator("#analystStatus")).to_contain_text("workspace or dataset changed")
    assert store.db.business_definitions.count_documents({}) == 0
    pw.expect(page.locator("#definitionConfirmation")).to_be_hidden()
    assert errors == []


def test_mobile_layout_and_escaping(ui):
    page, _, _, _, errors = ui
    page.set_viewport_size({"width": 390, "height": 844})
    ask(page)
    pw.expect(page.locator("#interpretationChoices .analyst-card")).to_have_count(2)
    page.wait_for_function("document.documentElement.scrollWidth <= window.innerWidth")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    capture(page, "phase-5-mobile.png")
    page.locator("#question").fill('<img src=x onerror="window.uiInjected=true">')
    page.locator("#askButton").click()
    pw.expect(page.locator("#answer")).to_contain_text("INSUFFICIENT DATA")
    assert page.evaluate("window.uiInjected === undefined")
    assert errors == []


def test_report_download_and_regeneration(ui):
    page, store, _, _, errors = ui
    page.locator('nav a[data-page="exports"]').click()
    with page.expect_download() as download:
        page.locator("#generateReportLink").click()
    assert download.value.suggested_filename == "AI_Business_Report.pdf"
    page.locator('nav a[data-page="assistant"]').click()
    pw.expect(page.locator("#analystReportHistory .analyst-card")).to_have_count(1)
    with page.expect_download():
        page.locator('[data-action="report"]').click()
    pw.expect(page.locator("#analystReportHistory .analyst-card")).to_have_count(2)
    assert store.db.reports.count_documents({"recomputed_from": {"$ne": None}}) == 1
    assert errors == []

def test_recalculation_conflict_discards_the_old_preview(ui):
    page, store, (workspace, dataset), _, errors = ui
    store.save_definition(workspace, dataset, "sales", "Net Sales", "revenue", 0, "Analyst")
    page.locator("#refreshAnalyst").click()
    pw.expect(page.locator("#savedDefinitions")).to_contain_text("sales → Net Sales")
    ask(page)
    qid = store.db.ai_queries.find_one({"definition.selection": "saved definition"})["query_id"]
    page.locator(f'[data-action="preview"][data-id="{qid}"]').click()
    pw.expect(page.locator("#recomputeReview")).to_be_visible()
    count = store.db.ai_queries.count_documents({})
    store.save_definition(workspace, dataset, "sales", "Gross Sales", "revenue", 1, "Other analyst")
    page.locator("#confirmRecompute").click()
    pw.expect(page.locator("#analystStatus")).to_contain_text("fresh preview")
    pw.expect(page.locator("#recomputeReview")).to_be_hidden()
    assert store.db.ai_queries.count_documents({}) == count
    assert errors == []


def test_failed_question_request_clears_obsolete_choices_and_busy_state(ui):
    page, _, _, _, errors = ui
    ask(page)
    pw.expect(page.locator("#interpretationChoices .analyst-card")).to_have_count(2)
    page.route("**/api/ask", lambda route: route.fulfill(status=503, content_type="application/json", body='{"error":"Temporary test failure"}'))
    page.locator("#question").fill("What is profit?")
    page.locator("#askButton").click()
    pw.expect(page.locator("#answer")).to_contain_text("Temporary test failure")
    pw.expect(page.locator("#interpretationChoices .analyst-card")).to_have_count(0)
    pw.expect(page.locator("#askButton")).to_be_enabled()
    assert errors == []

def test_ordinary_question_phrasing_reaches_the_same_definition_controls(ui):
    page, store, (workspace, dataset), _, errors = ui
    ask(page, "How much sales did we earn?")
    pw.expect(page.locator("#interpretationChoices .analyst-card")).to_have_count(2)
    page.locator('[data-action="remember"][data-index="1"]').click()
    page.locator("#confirmDefinition").click()
    pw.expect(page.locator("#savedDefinitions")).to_contain_text("sales → Net Sales")
    ask(page, "Show me sales for each region")
    pw.expect(page.locator("#answer")).to_contain_text("790.00")
    pw.expect(page.locator("#answerFreshness")).to_contain_text("saved version 1")
    ask(page, "Could you show me the total Gross Sales please?")
    pw.expect(page.locator("#answer")).to_contain_text("1,000.00")
    assert errors == []

def test_explicit_scope_controls_preserve_scope_when_choosing_an_interpretation(ui):
    page, store, _, current, errors = ui
    current["frame"]["Order Date"] = ["2025-01-01", "2025-01-31", "2025-02-01", "2025-02-28"]
    page.locator("#refreshAnalyst").click()
    pw.expect(page.locator("#scopeDateColumn option")).to_have_count(2)
    page.locator("#analystScopeControls summary").click()
    page.locator("#scopeRegionColumn").select_option("Region")
    page.locator("#scopeRegionValues").select_option("North")
    page.locator("#scopeDateColumn").select_option("Order Date")
    page.locator("#scopeStart").fill("2025-02-01")
    page.locator("#scopeEnd").fill("2025-02-28")
    page.locator("#scopeBaselineStart").fill("2025-01-01")
    page.locator("#scopeBaselineEnd").fill("2025-01-31")
    capture(page, "phase-8-scope-controls.png", "#analystScopeControls")
    ask(page)
    pw.expect(page.locator("#interpretationChoices .analyst-card")).to_have_count(2)
    pw.expect(page.locator("#answer")).to_contain_text("only the current period")
    # Changing controls does not rewrite the scope of an already asked question.
    page.locator("#clearAnalystScope").click()
    page.locator('[data-action="choose"][data-index="1"]').click()
    pw.expect(page.locator("#answer")).to_contain_text("current 250.00; baseline 90.00")
    pw.expect(page.locator("#answer")).to_contain_text("Matching rows: 1 current, 1 baseline")
    latest = store.db.ai_queries.find_one({"answerability": "OK"})
    assert latest["request_scope"]["filters"] == {"Region": ["North"]}
    assert latest["request_scope"]["compare_to"]["start"] == "2025-01-01"
    capture(page, "phase-8-comparison.png", ".assistant")
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_function("document.documentElement.scrollWidth <= window.innerWidth")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert errors == []


def test_incomplete_date_controls_do_not_send_an_unfiltered_question(ui):
    page, store, _, current, errors = ui
    current["frame"]["Order Date"] = ["2025-01-01"] * 4
    page.locator("#refreshAnalyst").click()
    pw.expect(page.locator("#scopeDateColumn option")).to_have_count(2)
    page.locator("#analystScopeControls summary").click()
    page.locator("#scopeDateColumn").select_option("Order Date")
    page.locator("#scopeStart").fill("2025-01-01")
    ask(page)
    pw.expect(page.locator("#analystStatus")).to_contain_text("both current-period dates")
    assert store.db.ai_queries.count_documents({}) == 0
    assert errors == []

def test_general_semicolon_upload_and_role_confirmation_in_browser(ui, monkeypatch):
    page, store, _, current, errors = ui
    server=importlib.import_module('server')
    monkeypatch.setattr(server,'financial_dashboard_available',current['real_financial_gate'])
    monkeypatch.setattr(server,'analysis_payload',current['real_analysis_payload'])
    monkeypatch.setattr(server,'dataset_from_request',current['real_dataset_from_request'])
    monkeypatch.setattr(server,'persist_active_dataset',lambda *args: None)
    monkeypatch.setitem(server.ACTIVE_DATASET,'df',None)
    monkeypatch.setitem(server.ACTIVE_DATASET,'source',None)
    raw=b'campaign;job;month\n2;admin.;may\n3;services;jun\n'
    page.locator('nav a[data-page="overview"]').click()
    page.locator('#datasetFile').set_input_files({'name':'bank-example.csv','mimeType':'text/csv','buffer':raw})
    page.locator('#analyzeCsvButton').click()
    pw.expect(page.locator('#uploadStatus')).to_contain_text('Ready to explore')
    page.locator('nav a[data-page="data-intelligence"]').click()
    pw.expect(page.locator('[data-role-column="campaign"]')).to_be_visible()
    with page.expect_response('**/api/aura/inspect'):
        page.locator('[data-role-column="campaign"]').select_option('quantity')
    pw.expect(page.locator('[data-role-column="campaign"]')).to_have_value('quantity')
    with page.expect_response('**/api/aura/inspect'):
        page.locator('[data-role-column="job"]').select_option('category')
    page.locator('nav a[data-page="assistant"]').click()
    ask(page,'What is campaign?')
    pw.expect(page.locator('#answer')).to_contain_text('5.00')
    ask(page,'Show campaign by job')
    pw.expect(page.locator('#answer')).to_contain_text('Breakdown by job')
    assert list(server.ACTIVE_DATASET['df'].columns)==['campaign','job','month']
    assert 'Sales' not in server.ACTIVE_DATASET['df'].columns
    page.locator('nav a[data-page="exports"]').click()
    pw.expect(page.locator('#generateReportLink')).to_have_attribute('aria-disabled','true')
    pw.expect(page.locator('#reportAvailability')).to_contain_text('financial PDF report requires')
    assert store.db.reports.count_documents({})==0
    assert errors==[]


def test_explicit_retail_source_date_format_control(ui):
    page, _, _, current, errors=ui
    current['frame']['InvoiceDate']=['12/1/2010 8:26','12/31/2010 16:00','1/1/2011 8:00','1/31/2011 19:00']
    page.locator('#refreshAnalyst').click()
    pw.expect(page.locator('#scopeDateColumn option')).to_have_count(2)
    page.locator('#analystScopeControls summary').click()
    page.locator('#scopeDateColumn').select_option('InvoiceDate')
    page.locator('#scopeDateFormat').select_option('%m/%d/%Y %H:%M')
    page.locator('#scopeStart').fill('2011-01-01');page.locator('#scopeEnd').fill('2011-01-31')
    page.locator('#scopeBaselineStart').fill('2010-12-01');page.locator('#scopeBaselineEnd').fill('2010-12-31')
    ask(page,'What is gross sales?')
    pw.expect(page.locator('#answer')).to_contain_text('current 700.00; baseline 300.00')
    page.locator('#aiEvidence summary').click()
    pw.expect(page.locator('#aiEvidenceDetail')).to_contain_text('source_date_format')
    pw.expect(page.locator('#aiEvidenceDetail')).to_contain_text('%m/%d/%Y %H:%M')
    capture(page,'phase-9-real-format-control.png','#analystScopeControls')
    assert errors==[]


def test_empty_question_focus_and_keyboard_submission(ui):
    page, store, _, _, errors = ui
    page.locator('#askButton').click()
    pw.expect(page.locator('#questionError')).to_contain_text('Type or speak')
    pw.expect(page.locator('#question')).to_be_focused()
    pw.expect(page.locator('#question')).to_have_attribute('aria-invalid','true')
    assert store.db.ai_queries.count_documents({}) == 0
    page.locator('#question').fill('What is Gross Sales?')
    pw.expect(page.locator('#questionError')).to_be_hidden()
    page.locator('#question').press('Control+Enter')
    pw.expect(page.locator('#answer')).to_contain_text('1,000.00')
    pw.expect(page.locator('#answerOutcome')).to_contain_text('Calculated result')
    assert page.locator('#question').get_attribute('maxlength') == '2000'
    assert errors == []


@pytest.mark.parametrize('start,end,left,right,field,message', [
    ('2025-02-28','2025-02-01','','','scopeEnd','on or before'),
    ('2025-02-01','2025-02-28','2025-02-28','2025-03-01','scopeBaselineStart','do not overlap'),
    ('2025-02-01','2025-02-28','2025-01-31','2025-01-01','scopeBaselineEnd','on or before'),
])
def test_date_validation_focus_and_no_query(ui,start,end,left,right,field,message):
    page,store,_,current,errors=ui
    current['frame']['Order Date']=['2025-02-01']*4
    page.locator('#refreshAnalyst').click()
    pw.expect(page.locator('#scopeDateColumn option')).to_have_count(2)
    page.locator('#analystScopeControls summary').click()
    page.locator('#scopeDateColumn').select_option('Order Date')
    for name,value in [('scopeStart',start),('scopeEnd',end),('scopeBaselineStart',left),('scopeBaselineEnd',right)]:
        page.locator('#'+name).fill(value)
    ask(page)
    pw.expect(page.locator('#questionError')).to_contain_text(message)
    pw.expect(page.locator('#'+field)).to_be_focused()
    assert store.db.ai_queries.count_documents({})==0
    assert errors==[]


def test_scope_summary_is_for_next_question_and_clear_restores_all_rows(ui):
    page,_,_,_,errors=ui
    page.locator('#analystScopeControls summary').click()
    page.locator('#scopeRegionColumn').select_option('Region')
    page.locator('#scopeRegionValues').select_option('North')
    pw.expect(page.locator('#nextQuestionScope')).to_contain_text('Region: North')
    ask(page,'What is Gross Sales?')
    pw.expect(page.locator('#answer')).to_contain_text('400.00')
    page.locator('#clearAnalystScope').click()
    pw.expect(page.locator('#nextQuestionScope')).to_have_text('Next question: all uploaded rows.')
    pw.expect(page.locator('#answer')).to_contain_text('400.00')
    capture(page,'phase-11-desktop.png','.assistant')
    page.set_viewport_size({'width':390,'height':844})
    page.wait_for_function('document.documentElement.scrollWidth <= innerWidth')
    capture(page,'phase-11-mobile.png','.assistant')
    assert errors==[]


def test_busy_state_and_failed_request_recovery(ui):
    page,_,_,_,errors=ui
    pending=[]
    page.route('**/api/ask',lambda route: pending.append(route))
    page.locator('#question').fill('What is Gross Sales?')
    page.locator('#askButton').click()
    pw.expect(page.locator('#askButton')).to_have_text('Working…')
    pw.expect(page.locator('#question')).to_be_disabled()
    pw.expect(page.locator('#assistant')).to_have_attribute('aria-busy','true')
    pending[0].fulfill(status=503,content_type='application/json',body='{"error":"Please retry this request."}')
    pw.expect(page.locator('#askButton')).to_have_text('Ask about data')
    pw.expect(page.locator('#question')).to_be_enabled()
    pw.expect(page.locator('#answerOutcome')).to_be_hidden()
    pw.expect(page.locator('#answer')).to_contain_text('Please retry')
    page.unroute('**/api/ask')
    ask(page,'What is Gross Sales?')
    pw.expect(page.locator('#answer')).to_contain_text('1,000.00')
    assert errors==[]


def test_unsupported_question_explains_next_step(ui):
    page,_,_,_,errors=ui
    ask(page,'Why did our customers leave?')
    pw.expect(page.locator('#answerOutcome')).to_contain_text('could not be answered')
    pw.expect(page.locator('#voiceStatus')).to_contain_text('needs more information')
    assert errors==[]


def test_unsupported_file_keeps_existing_answer(ui):
    page,_,_,_,errors=ui
    ask(page,'What is Gross Sales?')
    pw.expect(page.locator('#answer')).to_contain_text('1,000.00')
    page.locator('nav a[data-page="overview"]').click()
    page.locator('#datasetFile').set_input_files({'name':'bad.txt','mimeType':'text/plain','buffer':b'x'})
    page.locator('#analyzeCsvButton').click()
    pw.expect(page.locator('#uploadStatus')).to_contain_text('Choose a CSV, Excel or JSON')
    page.locator('nav a[data-page="assistant"]').click()
    pw.expect(page.locator('#answer')).to_contain_text('1,000.00')
    assert errors==[]


def test_failed_replacement_upload_keeps_existing_answer(ui):
    page,_,_,_,errors=ui
    ask(page,'What is Gross Sales?')
    pw.expect(page.locator('#answer')).to_contain_text('1,000.00')
    page.route('**/api/upload', lambda route: route.fulfill(status=400,content_type='application/json',body='{"error":"Invalid replacement dataset."}'))
    page.locator('nav a[data-page="overview"]').click()
    page.locator('#datasetFile').set_input_files({'name':'replacement.csv','mimeType':'text/csv','buffer':b'bad'})
    page.locator('#analyzeCsvButton').click()
    pw.expect(page.locator('#uploadStatus')).to_contain_text('Invalid replacement')
    page.locator('nav a[data-page="assistant"]').click()
    pw.expect(page.locator('#answer')).to_contain_text('1,000.00')
    assert errors==[]


def real_empty_workspace(ui, monkeypatch):
    page,_,_,current,_=ui
    server=importlib.import_module('server')
    monkeypatch.setattr(server,'financial_dashboard_available',current['real_financial_gate'])
    monkeypatch.setattr(server,'analysis_payload',current['real_analysis_payload'])
    monkeypatch.setattr(server,'dataset_from_request',current['real_dataset_from_request'])
    monkeypatch.setattr(server,'persist_active_dataset',lambda *args:None)
    monkeypatch.setitem(server.ACTIVE_DATASET,'df',None)
    monkeypatch.setitem(server.ACTIVE_DATASET,'source',None)
    page.goto(page.url.split('#')[0]+'#overview')
    page.reload()
    pw.expect(page.locator('#sourceLabel')).to_have_text('No file added yet')
    return server


def test_simple_navigation_help_and_empty_pages(ui,monkeypatch):
    page,_,_,_,errors=ui
    real_empty_workspace(ui,monkeypatch)
    assert page.locator('#primaryNavigation a').all_text_contents()==['Start','My data','Results','Ask a question','Download']
    assert page.locator('#advancedNavigation').evaluate('element => element.open') is False
    pw.expect(page.locator('#analyzeCsvButton')).to_be_disabled()
    page.locator('#openQuickHelp').click();pw.expect(page.locator('#quickHelp')).to_be_visible()
    page.locator('#closeQuickHelp').click();pw.expect(page.locator('#quickHelp')).to_be_hidden()
    for name in ['dashboard','data-intelligence','assistant','exports']:
        page.locator(f'#primaryNavigation a[data-page="{name}"]').click()
        pw.expect(page.locator(f'[data-page-content="{name}"] [data-empty-state]')).to_be_visible()
        pw.expect(page.locator(f'[data-page-content="{name}"] [data-needs-data]')).to_be_hidden()
    page.locator('#primaryNavigation a[data-page="overview"]').click()
    capture_workspace(page,'simple-start-desktop.png')
    assert errors==[]


def test_guided_upload_results_examples_and_download(ui,monkeypatch):
    page,store,_,_,errors=ui
    real_empty_workspace(ui,monkeypatch)
    page.locator('#datasetFile').set_input_files({'name':'my-units.csv','mimeType':'text/csv','buffer':b'Quantity,Region\n5,North\n7,South\n'})
    pw.expect(page.locator('#analyzeCsvButton')).to_be_enabled()
    page.locator('#analyzeCsvButton').click()
    pw.expect(page.locator('#currentPageTitle')).to_have_text('Results')
    pw.expect(page.locator('#generalResults')).to_be_visible()
    pw.expect(page.locator('#financialResults')).to_be_hidden()
    pw.expect(page.locator('#simpleNumberSummary')).to_contain_text('Quantity')
    pw.expect(page.locator('#simpleNumberSummary')).to_contain_text('6')
    capture_workspace(page,'simple-results-desktop.png')
    page.locator('#primaryNavigation a[data-page="data-intelligence"]').click()
    pw.expect(page.locator('#simpleDataPreview')).to_contain_text('North')
    pw.expect(page.get_by_label('Meaning of Quantity')).to_have_value('quantity')
    page.locator('#primaryNavigation a[data-page="assistant"]').click()
    assert page.locator('#savedMeanings').evaluate('element => element.open') is False
    page.get_by_role('button',name='Total Quantity',exact=True).click()
    pw.expect(page.locator('#question')).to_have_value('What is Quantity?')
    page.locator('#askButton').click();pw.expect(page.locator('#answer')).to_contain_text('12.00')
    capture_workspace(page,'simple-question-desktop.png')
    page.locator('#primaryNavigation a[data-page="exports"]').click()
    pw.expect(page.locator('#generateReportLink')).to_have_attribute('aria-disabled','true')
    pw.expect(page.locator('#reportAvailability')).to_contain_text('download your data as CSV')
    with page.expect_download() as downloaded:
        page.get_by_role('link',name='Download data (CSV)',exact=True).click()
    assert downloaded.value.suggested_filename=='source_dataset.csv'
    assert store.db.reports.count_documents({})==0
    assert errors==[]


def test_sample_button_is_a_complete_starting_path(ui,monkeypatch,tmp_path):
    page,_,_,_,errors=ui
    server=real_empty_workspace(ui,monkeypatch)
    sample=tmp_path/'sample.csv';sample.write_text('Quantity,Region\n5,North\n7,South\n')
    monkeypatch.setattr(server,'DATA_PATH',sample)
    page.get_by_role('button',name='Try sample data',exact=True).click()
    pw.expect(page.locator('#currentPageTitle')).to_have_text('Results')
    pw.expect(page.locator('#generalResults')).to_be_visible()
    page.locator('#primaryNavigation a[data-page="overview"]').click()
    pw.expect(page.locator('#uploadNextSteps')).to_be_visible()
    pw.expect(page.locator('#readyFileSummary')).to_contain_text('2 rows')
    assert errors==[]


def test_mobile_simple_navigation_and_unknown_link_recovery(ui,monkeypatch):
    page,_,_,_,errors=ui
    real_empty_workspace(ui,monkeypatch)
    page.set_viewport_size({'width':390,'height':844})
    for name in ['overview','data-intelligence','dashboard','assistant','exports']:
        pw.expect(page.locator(f'#primaryNavigation a[data-page="{name}"]')).to_be_in_viewport()
    page.wait_for_function('document.documentElement.scrollWidth <= innerWidth')
    capture_workspace(page,'simple-start-mobile.png')
    page.goto(page.url.split('#')[0]+'#unknown%22]')
    pw.expect(page.locator('#currentPageTitle')).to_have_text('Start here')
    assert page.url.endswith('#overview')
    page.locator('#advancedNavigation summary').click()
    page.locator('nav a[data-page="research"]').click()
    pw.expect(page.locator('#research')).to_be_visible()
    assert errors==[]


def test_import_busy_state_prevents_competing_uploads(ui,monkeypatch):
    page,_,_,_,errors=ui
    real_empty_workspace(ui,monkeypatch)
    pending=[];page.route('**/api/upload',lambda route:pending.append(route))
    page.locator('#datasetFile').set_input_files({'name':'file.csv','mimeType':'text/csv','buffer':b'Quantity\n5\n'})
    page.locator('#analyzeCsvButton').click()
    pw.expect(page.locator('#analyzeCsvButton')).to_have_text('Reading your file…')
    pw.expect(page.locator('#demoButton')).to_be_disabled()
    pw.expect(page.locator('#datasetFile')).to_be_disabled()
    pending[0].fulfill(status=400,content_type='application/json',body='{"error":"Please check this file."}')
    pw.expect(page.locator('#uploadStatus')).to_contain_text('Please check')
    pw.expect(page.locator('#datasetFile')).to_be_enabled()
    pw.expect(page.locator('#demoButton')).to_be_enabled()
    assert errors==[]


def capture_workspace(page,name):
    target=os.getenv('AURA_UI_CAPTURE_DIR')
    if target:
        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(Path(target)/name),full_page=True)


def test_number_summary_excludes_identifiers_and_year_codes(ui,monkeypatch):
    page,_,_,_,errors=ui
    real_empty_workspace(ui,monkeypatch)
    raw=b'Quantity,Region,year,customer_id\n5,North,2025,111\n7,South,2026,222\n'
    page.locator('#datasetFile').set_input_files({'name':'codes.csv','mimeType':'text/csv','buffer':raw})
    page.locator('#analyzeCsvButton').click()
    pw.expect(page.locator('#simpleNumberSummary tbody tr')).to_have_count(1)
    pw.expect(page.locator('#simpleNumberSummary')).to_contain_text('Quantity')
    pw.expect(page.locator('#simpleNumberSummary')).not_to_contain_text('customer_id')
    pw.expect(page.locator('#simpleNumberSummary')).not_to_contain_text('year')
    assert errors==[]
