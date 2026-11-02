"""Temporary anonymous public workspace without exposing existing private accounts."""
from io import BytesIO
import importlib
from threading import Thread
import os
import mongomock
from mongomock.gridfs import enable_gridfs_integration
import pytest
from flask import Flask
from authentication import configure_authentication,provision_user,principal_scope,PUBLIC_DEMO_PRINCIPAL
from persistence.mongo import _set_test_client
from start import serve_options


@pytest.fixture
def demo(monkeypatch):
    enable_gridfs_integration();_set_test_client(mongomock.MongoClient(),'demo_test')
    server=importlib.import_module('server')
    monkeypatch.setitem(server.app.config,'AURA_PUBLIC_DEMO',True)
    monkeypatch.setitem(server.app.config,'AURA_AUTH_REQUIRED',False)
    monkeypatch.setitem(server.app.config,'SECRET_KEY','public-demo-test-signing-key-only-12345678')
    monkeypatch.setitem(server.app.config,'SESSION_COOKIE_SECURE',False)
    monkeypatch.setattr(server.GeminiEvidenceProvider,'explain',lambda *args:None)
    with principal_scope(PUBLIC_DEMO_PRINCIPAL):
        server.init_store();server.set_setting('current_user',{'name':'Public Demo','role':'Executive','workspace':'Public Demo'})
    return server


def import_quantity(client,value,headers=None):
    result=client.post('/api/upload',data={'dataset':(BytesIO(f'Quantity,Region\n{value},North\n'.encode()),'sample.csv')},headers=headers or {})
    assert result.status_code==200


def test_public_render_default_overrides_previously_required_login(monkeypatch):
    env={'RENDER':'true','PORT':'10000','AURA_AUTH_REQUIRED':'true','AURA_COOKIE_SECURE':'true','AURA_SECRET_KEY':'public-demo-test-signing-key-only-12345678','RENDER_EXTERNAL_HOSTNAME':'ai-bi-platform-gud0.onrender.com'}
    for key,value in env.items():monkeypatch.setenv(key,value)
    monkeypatch.delenv('AURA_PUBLIC_DEMO',raising=False)
    assert serve_options(env)['host']=='0.0.0.0'
    app=Flask(__name__);configure_authentication(app)
    assert app.config['AURA_PUBLIC_DEMO'] and not app.config['AURA_AUTH_REQUIRED']
    response=app.test_client().get('/api/auth/session',base_url='https://'+env['RENDER_EXTERNAL_HOSTNAME'])
    assert response.json=={'auth_required':False,'authenticated':False,'public_demo':True}


def test_visitors_share_demo_upload_without_login_or_request_token(demo):
    a=demo.app.test_client();b=demo.app.test_client()
    assert a.get('/api/auth/session').json['auth_required'] is False
    import_quantity(a,5)
    answer=b.post('/api/ask',json={'question':'What is Quantity?'})
    assert answer.status_code==200 and '5.00' in answer.json['answer']
    assert b.get('/api/platform/bootstrap').json['user']['name']=='Public Demo'
    assert b.post('/api/platform/connect',json={'database':'data/other.db','table':'orders'}).status_code==403
    assert b.post('/api/ask',json={'question':'What is Quantity?'},headers={'Origin':'https://other.example'}).status_code==403


def test_private_account_data_is_preserved_when_login_is_paused(demo,monkeypatch):
    provision_user('private-owner','private-test-password')
    monkeypatch.setitem(demo.app.config,'AURA_PUBLIC_DEMO',False)
    monkeypatch.setitem(demo.app.config,'AURA_AUTH_REQUIRED',True)
    private=demo.app.test_client();token=private.get('/api/auth/session').json['csrf_token']
    login=private.post('/api/auth/login',json={'username':'private-owner','password':'private-test-password'},headers={'X-CSRF-Token':token})
    import_quantity(private,99,{'X-CSRF-Token':login.json['csrf_token']})
    monkeypatch.setitem(demo.app.config,'AURA_PUBLIC_DEMO',True)
    monkeypatch.setitem(demo.app.config,'AURA_AUTH_REQUIRED',False)
    import_quantity(demo.app.test_client(),5)
    assert '5.00' in private.post('/api/ask',json={'question':'What is Quantity?'}).json['answer']
    demo.app.test_client().post('/api/reset')
    monkeypatch.setitem(demo.app.config,'AURA_PUBLIC_DEMO',False)
    monkeypatch.setitem(demo.app.config,'AURA_AUTH_REQUIRED',True)
    assert '99.00' in private.post('/api/ask',json={'question':'What is Quantity?'},headers={'X-CSRF-Token':login.json['csrf_token']}).json['answer']


def test_demo_startup_never_restores_shared_legacy_cache(demo,monkeypatch):
    monkeypatch.setattr(demo,'get_setting',lambda *args:pytest.fail('legacy data must not be opened'))
    demo.restore_active_dataset()


def test_browser_opens_demo_and_asks_without_signin(demo):
    from playwright.sync_api import sync_playwright,expect
    from werkzeug.serving import make_server
    http=make_server('127.0.0.1',0,demo.app,threaded=True)
    thread=Thread(target=http.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as runtime:
            browser=runtime.chromium.launch(headless=True,channel='msedge' if os.name=='nt' else 'chromium')
            page=browser.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('https://cdn.plot.ly/**',lambda route:route.fulfill(content_type='application/javascript',body='window.Plotly={newPlot:()=>Promise.resolve(),Plots:{resize:()=>{}}};'))
            page.goto(f'http://127.0.0.1:{http.server_port}/')
            expect(page.locator('#publicDemoNotice')).to_be_visible()
            expect(page.locator('#accountLogin')).not_to_be_visible()
            page.locator('#datasetFile').set_input_files({'name':'sample.csv','mimeType':'text/csv','buffer':b'Quantity,Region\n5,North\n'})
            page.locator('#analyzeCsvButton').click();expect(page.locator('#uploadStatus')).to_contain_text('Imported')
            page.locator('nav a[data-page="assistant"]').click()
            page.locator('#question').fill('What is Quantity?');page.locator('#askButton').click()
            expect(page.locator('#answer')).to_contain_text('5.00')
            assert errors==[]
            browser.close()
    finally:http.shutdown();thread.join(timeout=5)
