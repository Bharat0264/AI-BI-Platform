/* Existing Flask API, accessible controls, and explicit confirmation at each write. */
window.createAuraAnalyst = function ({ request, escapeHtml: esc, onAnswer, onStatus, reportUrl }) {
  const byId = id => document.getElementById(id);
  const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const roles = { sales: "revenue", revenue: "revenue", profit: "profit", cost: "cost", costs: "cost", quantity: "quantity" };
  let context = null, answers = [], reports = [], currentAnswer = null, question = "";
  let pending = null, replay = null, busy = false, epoch = 0, refreshId = 0, questionScope = null;

  function dateLabel(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value || "") : date.toLocaleString();
  }
  function status(message, error = false) {
    byId("analystStatus").textContent = message;
    byId("analystStatus").classList.toggle("error", error);
    if (byId("exports").classList.contains("active-page")) {
      byId("exportReportStatus").textContent = message;
      byId("exportReportStatus").classList.toggle("error", error);
    }
  }
  function syncButtons() {
    document.querySelectorAll("[data-analyst-action]").forEach(button => {
      button.disabled = busy || (!context && button.id !== "refreshAnalyst") || button.dataset.unavailable === "true";
    });
    document.querySelectorAll("[data-scope-input]").forEach(input => { input.disabled = busy || !context; });
    byId("askButton").disabled = busy;
    byId("askButton").textContent = busy ? "Working…" : "Ask about data";
    byId("assistant").setAttribute("aria-busy", String(busy));
    byId("question").disabled = busy;
    byId("definitionTerm").disabled = busy || !context;
    byId("definitionColumn").disabled = busy || !context;
    byId("confirmRecompute").disabled = busy || !replay?.canSave;
    byId("reviewDisable").disabled = busy || !context?.definitions?.[byId("definitionTerm").value];
  }
  async function run(action) {
    if (busy) return;
    const generation = epoch;
    busy = true; syncButtons();
    try { await action(generation); }
    catch (error) {
      if (generation === epoch) { status(error.message, true); onStatus(error.message, true);
        if (error.focusId) requestAnimationFrame(() => byId(error.focusId).focus()); }
    } finally {
      if (generation === epoch) {
        busy = false; syncButtons();
        if (pending && !byId("definitionConfirmation").hidden) byId("confirmDefinition").focus();
      }
    }
  }
  function badge(lifecycle) {
    const code = lifecycle?.status || "UNKNOWN";
    const labels = { CURRENT: "Current", STALE: "Needs updating", UNKNOWN: "Tracking incomplete", UNRESOLVED: "Needs clarification" };
    return `<span class="analyst-badge ${["CURRENT", "STALE", "UNKNOWN", "UNRESOLVED"].includes(code) ? code.toLowerCase() : "unknown"}">${esc(labels[code] || code)}</span>`;
  }
  function reasons(lifecycle) {
    const messages = new Set();
    function visit(items) {
      for (const reason of items || []) {
        const labels = {
          DIFFERENT_ACTIVE_SNAPSHOT: "Load the original dataset to recalculate this item.",
          DEFINITION_CHANGED: "A saved business definition changed or was disabled.",
          SEMANTIC_CORRECTION_CHANGED: "A source column's meaning was corrected.",
          LEGACY_UNTRACKED_ARTIFACT: "This older item has incomplete dependency tracking.",
          NO_RESOLVED_ANSWER: "Choose an interpretation before saving a final answer.",
          UNSELECTED_INTERPRETATION: "This interpretation has not been selected.",
        };
        if (labels[reason.code]) messages.add(labels[reason.code]);
        visit(reason.reasons);
      }
    }
    visit(lifecycle?.reasons);
    if (!messages.size && lifecycle?.status === "UNKNOWN") messages.add("Some dependencies could not be checked.");
    return [...messages].join(" ");
  }
  function differentSnapshot(item) { return !context || item.dataset_id !== context.dataset_id; }
  function clearConfirmation() { pending = null; byId("definitionConfirmation").hidden = true; }
  function clearReplay() { replay = null; byId("recomputeReview").hidden = true; syncButtons(); }
  function fillColumns(preferred) {
    const term = byId("definitionTerm").value;
    const selected = preferred || context?.definitions?.[term]?.measure_column || "";
    const columns = (context?.semantic_schema || []).filter(field => field.semantic_role === roles[term]);
    byId("definitionColumn").innerHTML = `<option value="">Choose a column</option>` + columns.map(field => `<option value="${esc(field.column)}" ${field.column === selected ? "selected" : ""}>${esc(field.column)}</option>`).join("");
    syncButtons();
  }
  function fillScopeValues(kind, preferred = []) {
    const column = byId(`scope${kind}Column`).value;
    const option = context?.scope_options?.filter_columns?.find(item => item.column === column);
    byId(`scope${kind}Values`).innerHTML = (option?.values || []).map(value => `<option value="${esc(value)}" ${preferred.includes(value) ? "selected" : ""}>${esc(value)}</option>`).join("");
    byId("scopeOptionsNote").textContent = context?.scope_options?.filter_columns?.some(item => item.truncated)
      ? "Some columns show only their first 200 distinct labels. The API can select other known labels explicitly." : "Scope is applied when you ask. Choosing an interpretation reuses that question's original scope.";
  }
  function fillScopeControls() {
    for (const kind of ["Region", "Category"]) {
      const chosen = byId(`scope${kind}Column`).value;
      const values = [...byId(`scope${kind}Values`).selectedOptions].map(option => option.value);
      const options = (context?.scope_options?.filter_columns || []).filter(item => item.role === kind.toLowerCase());
      byId(`scope${kind}Column`).innerHTML = `<option value="">No ${kind.toLowerCase()} filter</option>` + options.map(item => `<option value="${esc(item.column)}" ${item.column === chosen ? "selected" : ""}>${esc(item.column)}</option>`).join("");
      fillScopeValues(kind, values);
    }
    const chosen = byId("scopeDateColumn").value;
    byId("scopeDateColumn").innerHTML = `<option value="">No date period</option>` + (context?.scope_options?.date_columns || []).map(column => `<option value="${esc(column)}" ${column === chosen ? "selected" : ""}>${esc(column)}</option>`).join("");
  }
  function clearQuestionError() {
    byId("questionError").hidden = true;
    byId("questionError").textContent = "";
    document.querySelectorAll('#assistant [aria-invalid="true"]').forEach(input => input.removeAttribute("aria-invalid"));
  }
  function invalidQuestion(message, id) {
    byId("questionError").textContent = message;
    byId("questionError").hidden = false;
    byId(id).setAttribute("aria-invalid", "true");
    if (byId(id).matches("[data-scope-input]")) byId("analystScopeControls").open = true;
    const error = new Error(message); error.focusId = id; throw error;
  }
  function updateScopeSummary() {
    const parts = [];
    for (const kind of ["Region", "Category"]) {
      const column = byId(`scope${kind}Column`).value;
      const values = [...byId(`scope${kind}Values`).selectedOptions].map(option => option.value);
      if (column && values.length) parts.push(`${column}: ${values.join(", ")}`);
    }
    const date = byId("scopeDateColumn").value, start = byId("scopeStart").value, end = byId("scopeEnd").value;
    const left = byId("scopeBaselineStart").value, right = byId("scopeBaselineEnd").value;
    if (date || start || end || left || right) {
      parts.push(date && start && end ? `${date}: ${start} to ${end}` : "date period incomplete — choose a column, start and end");
      if (left || right) parts.push(left && right ? `compare with ${left} to ${right}` : "comparison dates incomplete");
    }
    byId("nextQuestionScope").textContent = `Next question: ${parts.length ? parts.join(" · ") : "all uploaded rows"}.`;
  }
  function readScope() {
    const filters = {};
    for (const kind of ["Region", "Category"]) {
      const column = byId(`scope${kind}Column`).value;
      const values = [...byId(`scope${kind}Values`).selectedOptions].map(option => option.value);
      if (column && values.length) filters[column] = values;
    }
    const date = byId("scopeDateColumn").value, start = byId("scopeStart").value, end = byId("scopeEnd").value;
    const baselineStart = byId("scopeBaselineStart").value, baselineEnd = byId("scopeBaselineEnd").value;
    const scope = { ...(Object.keys(filters).length ? { filters } : {}) };
    if (date || start || end || baselineStart || baselineEnd) {
      if (!date || !start || !end) invalidQuestion("Choose a date column and both current-period dates.", !date ? "scopeDateColumn" : !start ? "scopeStart" : "scopeEnd");
      if (start > end) invalidQuestion("Current period start must be on or before its end.", "scopeEnd");
      scope.date_column = date; scope.period = { start, end };
      const format = byId("scopeDateFormat").value;
      if (format !== "ISO") scope.date_format = format;
      if (baselineStart || baselineEnd) {
        if (!baselineStart || !baselineEnd) invalidQuestion("Provide both baseline dates or leave both blank.", !baselineStart ? "scopeBaselineStart" : "scopeBaselineEnd");
        if (baselineStart > baselineEnd) invalidQuestion("Comparison start must be on or before its end.", "scopeBaselineEnd");
        if (start <= baselineEnd && baselineStart <= end) invalidQuestion("Choose comparison dates that do not overlap the current period.", "scopeBaselineStart");
        scope.compare_to = { start: baselineStart, end: baselineEnd };
      }
    }
    return Object.keys(scope).length ? scope : null;
  }
  function clearScope() {
    for (const kind of ["Region", "Category"]) { byId(`scope${kind}Column`).value = ""; fillScopeValues(kind); }
    for (const id of ["scopeDateColumn", "scopeStart", "scopeEnd", "scopeBaselineStart", "scopeBaselineEnd"]) byId(id).value = "";
    byId("scopeDateFormat").value = "ISO";
    updateScopeSummary(); clearQuestionError();
  }
  function renderHistories() {
    byId("analystAnswerHistory").innerHTML = answers.length ? answers.map(item => `<article class="analyst-card">
      <h4>${esc(item.question)}</h4>${badge(item.lifecycle)}<p>${esc(reasons(item.lifecycle))}</p>
      <small>${esc(dateLabel(item.created_at))}${item.recomputed_from ? " · Recalculated answer; original preserved" : ""}</small>
      <div class="analyst-actions"><button type="button" class="secondary" data-analyst-action data-action="view" data-id="${esc(item.query_id)}">View answer</button>
      <button type="button" data-analyst-action data-action="preview" data-id="${esc(item.query_id)}" data-unavailable="${differentSnapshot(item) || !("request_definition" in item)}">Preview recalculation</button></div></article>`).join("") : `<p class="muted">No saved answers in this workspace yet.</p>`;
    byId("analystReportHistory").innerHTML = reports.length ? reports.map(item => `<article class="analyst-card"><h4>Business report · ${esc(dateLabel(item.created_at))}</h4>${badge(item.lifecycle)}<p>${esc(reasons(item.lifecycle))}</p><small>${item.recomputed_from ? "Regenerated copy; original preserved" : "Original export"}</small><div class="analyst-actions"><button type="button" data-analyst-action data-action="report" data-id="${esc(item.report_id)}" data-unavailable="${differentSnapshot(item) || !("filters" in item)}">Regenerate &amp; download</button></div></article>`).join("") : `<p class="muted">No tracked reports in this workspace yet.</p>`;
    syncButtons();
  }
  function renderAnswer(payload) {
    currentAnswer = payload;
    const outcomes = { OK: "Calculated result — review the evidence below.", CLARIFICATION_REQUIRED: "Choose a column meaning to continue.", "INSUFFICIENT DATA": "This question could not be answered from the available data. Try a total or average using an exact column name, or confirm column meanings in Data Intelligence." };
    byId("answerOutcome").textContent = outcomes[payload.status] || "Review this result and its evidence.";
    byId("answerOutcome").hidden = false;
    const impact = payload.interpretation_check?.impact;
    byId("answer").textContent = payload.status === "CLARIFICATION_REQUIRED" && payload.alternatives?.length
      ? (payload.request_scope?.compare_to ? "Choose a measure before comparing periods. These alternatives cover only the current period."
        : impact === "DIFFERENT_TESTED_OUTPUTS" ? "The answer changes depending on which column you mean. Choose a meaning below."
        : impact === "SAME_TESTED_OUTPUT" ? "These columns give the same tested output, but may have different business meanings. Choose which one you mean."
        : "Some interpretations could not be checked. Review the available results and choose a meaning below.")
      : payload.answer;
    byId("answerFreshness").innerHTML = badge(payload.lifecycle || { status: payload.status === "CLARIFICATION_REQUIRED" ? "UNRESOLVED" : "UNKNOWN" }) + (payload.definition ? `<p class="muted">Using ${esc(payload.definition.measure_column)} · ${esc(payload.definition.aggregation)}${payload.definition.saved_reference ? ` · saved version ${esc(payload.definition.saved_reference.version)}` : " · this question only"}</p>` : "");
    byId("aiEvidenceDetail").textContent = JSON.stringify({ definition: payload.definition, plan: payload.plan, evidence: payload.evidence, verification: payload.verification, interpretation_check: payload.interpretation_check }, null, 2);
    const citations = payload.citations || (payload.evidence || []).map(item => ({ label: "Computed evidence", value: item.evidence_id, source: item.method }));
    byId("answerCitations").innerHTML = citations.map(item => `<article><span>${esc(item.label)}</span><strong>${esc(item.value)}</strong><small>${esc(item.source)}</small></article>`).join("");
    const alternatives = payload.alternatives || [];
    const term = payload.clarification?.term;
    const snapshot = payload.dataset_id || payload.evidence?.[0]?.dataset_id;
    const unavailableSnapshot = !context || (snapshot && snapshot !== context.dataset_id);
    byId("interpretationChoices").innerHTML = alternatives.map((item, index) => `<article class="analyst-card"><h4>${esc(item.measure_column)}</h4><p>${esc(item.answer)}</p><div class="analyst-actions"><button type="button" data-analyst-action data-action="choose" data-index="${index}" data-unavailable="${item.status !== "OK" || unavailableSnapshot}">Use for this question</button>${roles[term] ? `<button type="button" class="secondary" data-analyst-action data-action="remember" data-index="${index}" data-unavailable="${item.status !== "OK" || unavailableSnapshot}">Remember as ${esc(term)}…</button>` : ""}</div></article>`).join("");
    onAnswer(payload.answer, false);
    syncButtons();
  }
  async function refresh() {
    const generation = epoch, sequence = ++refreshId;
    try {
      const [definitions, history, exports] = await Promise.all([request("/api/aura/definitions"), request("/api/aura/answers"), request("/api/aura/reports")]);
      if (generation !== epoch || sequence !== refreshId) return;
      if (definitions.dataset_id !== history.active_dataset_id || definitions.dataset_id !== exports.active_dataset_id) throw new Error("The dataset changed while loading. Refresh status again.");
      if (context && (context.dataset_id !== definitions.dataset_id || context.workspace_id !== definitions.workspace_id)) reset();
      context = definitions; answers = history.items || []; reports = exports.items || [];
      byId("definitionScope").textContent = `${definitions.workspace_name || "Current workspace"} / ${definitions.dataset_name || "Current dataset"} · Definitions apply only to this workspace and exact data snapshot. Saving a choice never changes the uploaded data.`;
      const saved = Object.values(definitions.definitions || {});
      byId("savedDefinitions").innerHTML = saved.length ? saved.map(item => `<article class="analyst-card"><strong>${esc(item.term)} → ${esc(item.measure_column)}</strong><p class="muted">Version ${esc(item.version)}</p></article>`).join("") : `<p class="muted">No saved defaults for this data snapshot.</p>`;
      fillColumns(byId("definitionColumn").value);
      fillScopeControls();
      updateScopeSummary(); renderHistories();
      if (currentAnswer?.query_id) {
        const id = currentAnswer.query_id;
        const latest = answers.find(item => item.query_id === id) || await request(`/api/aura/answers/${encodeURIComponent(id)}`);
        if (generation === epoch && currentAnswer?.query_id === id) renderAnswer({ ...currentAnswer, lifecycle: latest.lifecycle });
      }
      syncButtons();
    } catch (error) {
      if (generation === epoch && sequence === refreshId) {
        context = null; clearConfirmation(); clearReplay(); syncButtons();
        byId("answerFreshness").textContent = "Freshness could not be refreshed.";
        status(error.message, true);
      }
    }
  }
  function reset() {
    epoch++; refreshId++; busy = false; context = null; answers = []; reports = []; currentAnswer = null; question = "";
    clearConfirmation(); clearReplay(); clearScope(); questionScope = null;
    byId("answerOutcome").hidden = true;
    for (const id of ["answer", "answerFreshness", "answerCitations", "aiEvidenceDetail", "interpretationChoices", "savedDefinitions", "definitionHistory"]) byId(id).textContent = "";
    byId("analystAnswerHistory").textContent = "Load a dataset to see its workspace history.";
    byId("analystReportHistory").textContent = "No reports loaded.";
    byId("definitionScope").textContent = "Definitions stay within the workspace and exact dataset snapshot.";
    fillColumns(); status(""); onAnswer("", false); syncButtons();
  }
  async function submit(text, definition, generation, speak, scope = null) {
    clearConfirmation(); clearReplay(); byId("interpretationChoices").textContent = "";
    byId("answerFreshness").textContent = ""; byId("answerCitations").textContent = ""; byId("aiEvidenceDetail").textContent = "";
    byId("answerOutcome").hidden = true;
    byId("answer").textContent = "Calculating from your data…"; onStatus("Calculating…");
    currentAnswer = null;
    let payload;
    try { payload = await request("/api/ask", json("POST", { question: text, ...(definition ? { definition } : {}), ...(scope ? { scope } : {}), ...(context ? { expected_dataset_id: context.dataset_id, expected_workspace_id: context.workspace_id } : {}) })); }
    catch (error) { if (generation === epoch) { byId("answer").textContent = error.message; onAnswer("", false); } throw error; }
    if (generation !== epoch) return;
    question = text; questionScope = scope; renderAnswer(payload);
    onStatus(payload.status === "CLARIFICATION_REQUIRED" ? "Choose the meaning of your measure below." : payload.status === "OK" ? "Answer ready." : "This question needs more information. Review the result below.");
    onAnswer(payload.answer, speak); await refresh();
  }
  function ask(text, { speak = true } = {}) {
    return run(generation => {
      clearQuestionError();
      if (!text.trim()) invalidQuestion("Type or speak a business question first.", "question");
      if (text.length > 2000) invalidQuestion("Keep your question within 2,000 characters.", "question");
      return submit(text, null, generation, speak, readScope());
    });
  }
  async function reviewDefinition(method, generation, term, column) {
    if (!context) throw new Error("Refresh the dataset before choosing a definition.");
    const scope = context.dataset_id;
    const history = await request(`/api/aura/definitions?term=${encodeURIComponent(term)}`);
    if (generation !== epoch || scope !== context?.dataset_id) return;
    if (history.dataset_id !== scope || history.workspace_id !== context.workspace_id) throw new Error("The workspace or dataset changed. Refresh status and review again.");
    const latest = history.history.at(-1);
    if (method === "PUT" && !column) throw new Error("Choose a column first.");
    if (method === "DELETE" && !latest?.active) throw new Error("There is no active default to disable.");
    pending = { method, term, column, version: latest?.version || 0, dataset: scope, workspace: context.workspace_id };
    byId("definitionConfirmationText").textContent = method === "PUT"
      ? `Remember “${term}” as “${column}” for ${context.workspace_name || "this workspace"} / ${context.dataset_name || "this dataset"}? ${latest?.active ? `This replaces ${latest.measure_column} (version ${latest.version}).` : "This creates a new active default."} Future questions using this term will use that column. Original answers stay in history.`
      : `Disable the saved meaning of “${term}” (version ${latest.version})? Its history stays available; future ambiguous questions will ask for clarification.`;
    byId("definitionConfirmation").hidden = false;
    byId("confirmDefinition").textContent = method === "DELETE" ? "Confirm disabling default" : "Confirm & save";
    byId("confirmDefinition").focus();
  }
  async function confirmDefinition(generation) {
    const choice = pending;
    if (!choice || choice.dataset !== context?.dataset_id) throw new Error("Review the definition again before saving.");
    try {
      const payload = await request("/api/aura/definitions", json(choice.method, { term: choice.term, ...(choice.method === "PUT" ? { measure_column: choice.column } : {}), expected_version: choice.version, confirmed: true, expected_dataset_id: choice.dataset, expected_workspace_id: choice.workspace }));
      if (generation !== epoch) return;
      clearConfirmation(); byId("definitionHistory").textContent = ""; await refresh();
      status(`Definition ${choice.method === "PUT" ? "saved" : "disabled"} as version ${payload.definition.version}. Earlier answers are preserved; check their status below.`);
    } catch (error) {
      if (generation !== epoch) return;
      clearConfirmation(); await refresh();
      status(error.message, true); onStatus(error.message, true);
    }
  }
  async function preview(id, generation) {
    clearReplay();
    const original = await request(`/api/aura/answers/${encodeURIComponent(id)}`);
    const payload = await request(`/api/aura/answers/${encodeURIComponent(id)}/recompute`, json("POST", {}));
    if (generation !== epoch) return;
    replay = { id, token: payload.review_token, canSave: payload.preview.status === "OK" && payload.preview.verification?.status === "SUPPORTED" };
    byId("recomputeOriginal").textContent = original.response;
    byId("recomputePreview").textContent = payload.preview.answer;
    byId("recomputeReview").hidden = false;
    byId("recomputeReview").scrollIntoView({ block: "center", behavior: "smooth" });
    status(replay.canSave ? "Review the original and new result before saving." : "This result still needs clarification. Confirm a definition or ask a new question first.");
  }
  async function confirmReplay(generation) {
    const reviewed = replay;
    if (!reviewed?.canSave) throw new Error("Review a supported recalculation first.");
    try {
      const payload = await request(`/api/aura/answers/${encodeURIComponent(reviewed.id)}/recompute`, json("POST", { confirmed: true, review_token: reviewed.token }));
      if (generation !== epoch) return;
      clearReplay(); renderAnswer(payload); await refresh();
      status("New answer saved. The original answer remains in history.");
    } catch (error) { clearReplay(); throw error; }
  }
  async function downloadReport(id, generation) {
    const url = id ? `/api/report?recomputed_from=${encodeURIComponent(id)}` : reportUrl();
    status("Generating a separate report file…");
    const response = await fetch(url);
    if (!response.ok) { const payload = await response.json().catch(() => ({})); throw new Error(payload.error || "Report generation failed."); }
    const blob = await response.blob();
    if (generation !== epoch) return;
    const href = URL.createObjectURL(blob), anchor = document.createElement("a");
    anchor.href = href; anchor.download = "AI_Business_Report.pdf"; document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(href), 1000);
    await refresh();
    status(response.headers.get("X-AURA-Freshness") === "STALE" ? "Report downloaded, but a dependency changed during export. Refresh and review its status." : "Report downloaded. Earlier files and report records are preserved.");
  }
  async function handleAction(event) {
    const button = event.target.closest("[data-action]");
    if (!button || button.disabled) return;
    await run(async generation => {
      const { action, id, index } = button.dataset;
      if (action === "choose" || action === "remember") {
        const alternative = currentAnswer?.alternatives?.[Number(index)];
        if (!alternative || alternative.status !== "OK") throw new Error("Choose a computed interpretation first.");
        if (action === "choose") await submit(question, { measure_column: alternative.measure_column }, generation, false, questionScope);
        else {
          byId("definitionTerm").value = currentAnswer.clarification.term; fillColumns(alternative.measure_column);
          await reviewDefinition("PUT", generation, currentAnswer.clarification.term, alternative.measure_column);
          byId("definitionConfirmation").scrollIntoView({ block: "center", behavior: "smooth" });
        }
      } else if (action === "view") {
        const item = await request(`/api/aura/answers/${encodeURIComponent(id)}`);
        if (generation !== epoch) return;
        question = item.question; questionScope = item.request_scope || null; byId("question").value = question;
        clearConfirmation(); clearReplay(); renderAnswer({ ...item, query_id: item.query_id, answer: item.response, status: item.answerability });
        byId("answer").scrollIntoView({ block: "center", behavior: "smooth" });
      } else if (action === "preview") await preview(id, generation);
      else if (action === "report") await downloadReport(id, generation);
    });
  }
  document.querySelectorAll("[data-scope-input]").forEach(input => input.addEventListener("change", () => { clearQuestionError(); updateScopeSummary(); }));
  document.querySelectorAll("[data-scope-input]").forEach(input => input.addEventListener("input", updateScopeSummary));
  byId("question").addEventListener("input", clearQuestionError);
  byId("question").addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !event.isComposing) { event.preventDefault(); byId("askButton").click(); }
  });
  for (const kind of ["Region", "Category"]) byId(`scope${kind}Column`).addEventListener("change", () => { fillScopeValues(kind); updateScopeSummary(); });
  byId("clearAnalystScope").addEventListener("click", clearScope);
  byId("interpretationChoices").addEventListener("click", handleAction);
  byId("analystWorkspace").addEventListener("click", handleAction);
  byId("definitionTerm").addEventListener("change", () => { clearConfirmation(); byId("definitionHistory").textContent = ""; fillColumns(); });
  byId("definitionColumn").addEventListener("change", clearConfirmation);
  byId("refreshAnalyst").addEventListener("click", () => run(async () => { clearConfirmation(); clearReplay(); await refresh(); }));
  byId("reviewDefinition").addEventListener("click", () => run(generation => reviewDefinition("PUT", generation, byId("definitionTerm").value, byId("definitionColumn").value)));
  byId("reviewDisable").addEventListener("click", () => run(generation => reviewDefinition("DELETE", generation, byId("definitionTerm").value)));
  byId("confirmDefinition").addEventListener("click", () => run(confirmDefinition));
  byId("cancelDefinition").addEventListener("click", clearConfirmation);
  byId("viewDefinitionHistory").addEventListener("click", () => run(async generation => {
    const payload = await request(`/api/aura/definitions?term=${encodeURIComponent(byId("definitionTerm").value)}`);
    if (generation !== epoch) return;
    byId("definitionHistory").innerHTML = payload.history.length ? payload.history.map(item => `<article class="analyst-card"><strong>Version ${esc(item.version)} · ${item.active ? "Confirmed" : "Disabled"}</strong><p>${esc(item.term)} → ${esc(item.measure_column)}</p><small>${esc(item.confirmed_by)} · ${esc(dateLabel(item.confirmed_at))}</small></article>`).join("") : `<p class="muted">No confirmations for this term yet.</p>`;
  }));
  byId("confirmRecompute").addEventListener("click", () => run(confirmReplay));
  byId("cancelRecompute").addEventListener("click", clearReplay);
  byId("generateReportLink").addEventListener("click", event => { event.preventDefault(); run(generation => downloadReport(null, generation)); });
  syncButtons();
  return { ask, refresh, reset };
};
