const platformState = { bootstrap: null, alertEvaluation: {}, metrics: [] };
const pstatus = (message, error = false) => {
  const el = document.getElementById("platformStatus");
  el.textContent = message; el.classList.toggle("error", error);
};
const api = (url, options = {}) => fetchJson(url, options);
const jsonOptions = (method, body) => ({ method, headers: {"Content-Type":"application/json"}, body: JSON.stringify(body) });
const recordPayload = record => record.payload || {};
const niceDate = value => new Date(value).toLocaleString();

document.querySelectorAll("[data-platform-tab]").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll("[data-platform-tab]").forEach(item => item.classList.toggle("active", item === button));
  document.querySelectorAll("[data-platform-pane]").forEach(pane => pane.classList.toggle("active", pane.dataset.platformPane === button.dataset.platformTab));
}));

function miniItem(title, detail, actions = "") {
  return `<article class="mini-item"><div><strong>${escapeHtml(title)}</strong><small>${escapeHtml(detail || "")}</small></div><div class="mini-actions">${actions}</div></article>`;
}

function renderPlatform(data) {
  platformState.bootstrap = data; platformState.metrics = data.semanticMetrics || [];
  const user = data.user || {};
  document.getElementById("profileName").value = user.name || "";
  document.getElementById("workspaceName").value = user.workspace || "";
  document.getElementById("profileRole").value = user.role || "Executive";
  document.getElementById("workspaceBadge").textContent = `${user.workspace || "Workspace"} · ${user.role || "Executive"}`;
  document.getElementById("dashboardList").innerHTML = `<h4>Saved dashboards</h4>` + (data.dashboards.length ? data.dashboards.map(r => miniItem(r.name, niceDate(r.created_at), `<button data-load-dashboard="${r.id}">Load</button><button class="danger" data-delete-record="dashboard:${r.id}">Delete</button>`)).join("") : `<p class="muted">No saved dashboards yet.</p>`);
  document.getElementById("historyList").innerHTML = `<h4>Recent analysis</h4>` + (data.historys.length ? data.historys.slice(0,8).map(r => miniItem(r.name, `${recordPayload(r).type || "Activity"} · ${niceDate(r.created_at)}`)).join("") : `<p class="muted">History appears as you work.</p>`);
  renderRecordList("actionList", data.actions, r => `${recordPayload(r).owner || "Unassigned"} · ${recordPayload(r).status || "Open"} · due ${recordPayload(r).due || "not set"}`, "action");
  renderRecordList("scheduleList", data.schedules, r => `${recordPayload(r).frequency || "Monthly"} · next run calculated on delivery`, "schedule");
  renderAlerts(data.alerts);
  renderMetrics();
  bindDynamicActions();
}

function renderRecordList(id, records, detail, kind) {
  document.getElementById(id).innerHTML = records.length ? records.map(r => miniItem(r.name, detail(r), `<button class="danger" data-delete-record="${kind}:${r.id}">Delete</button>`)).join("") : `<p class="muted">Nothing here yet.</p>`;
}
function renderAlerts(records) {
  document.getElementById("alertList").innerHTML = records.length ? records.map(r => {
    const p = recordPayload(r), ev = platformState.alertEvaluation[r.id];
    const detail = `${p.metric || "metric"} ${p.operator || "above"} ${p.threshold}` + (ev ? ` · current ${Number(ev.currentValue).toFixed(2)}` : "");
    return miniItem(`${ev?.triggered ? "● " : ""}${r.name}`, detail, `<button class="danger" data-delete-record="alert:${r.id}">Delete</button>`);
  }).join("") : `<p class="muted">No alert rules yet.</p>`;
}
function renderMetrics() {
  document.getElementById("metricList").innerHTML = platformState.metrics.map((m,i) => miniItem(m.name, m.formula || `${m.aggregation || "sum"}(${m.column || ""})`, `<button class="danger" data-remove-metric="${i}">Remove</button>`)).join("");
  document.querySelectorAll("[data-remove-metric]").forEach(b => b.onclick = async () => { platformState.metrics.splice(Number(b.dataset.removeMetric),1); await saveMetrics(); });
}

async function refreshPlatform(message) {
  const data = await api("/api/platform/bootstrap"); renderPlatform(data); if (message) pstatus(message);
}
async function createRecord(kind, body, message) {
  await api(`/api/platform/records/${kind}`, jsonOptions("POST", body)); await refreshPlatform(message);
}
async function deleteRecord(kind, id) {
  await api(`/api/platform/records/${kind}/${id}`, {method:"DELETE"}); await refreshPlatform("Record deleted.");
}
function bindDynamicActions() {
  document.querySelectorAll("[data-delete-record]").forEach(b => b.onclick = () => { const [kind,id] = b.dataset.deleteRecord.split(":"); deleteRecord(kind,id).catch(e=>pstatus(e.message,true)); });
  document.querySelectorAll("[data-load-dashboard]").forEach(b => b.onclick = async () => { try { const payload=await api(`/api/platform/dashboards/${b.dataset.loadDashboard}/load`,{method:"POST"}); state.selectedRegions=payload.selectedRegions; state.selectedCategories=payload.selectedCategories; render(payload); pstatus("Saved dashboard loaded."); } catch(e){pstatus(e.message,true);} });
}

document.getElementById("saveProfile").onclick = async () => { try { await api("/api/platform/user", jsonOptions("PUT", {name:profileName.value, workspace:workspaceName.value, role:profileRole.value})); await refreshPlatform("Workspace profile saved."); } catch(e){pstatus(e.message,true);} };
document.getElementById("saveDashboard").onclick = () => createRecord("dashboard", {name:dashboardName.value, regions:state.selectedRegions, categories:state.selectedCategories, source:document.getElementById("sourceLabel").textContent}, "Dashboard saved.").catch(e=>pstatus(e.message,true));
document.getElementById("createAlert").onclick = () => createRecord("alert", {name:alertName.value, metric:alertMetric.value, operator:alertOperator.value, threshold:Number(alertThreshold.value)}, "Alert created.").catch(e=>pstatus(e.message,true));
document.getElementById("createAction").onclick = () => createRecord("action", {name:actionName.value, owner:actionOwner.value, due:actionDue.value, impact:actionImpact.value, status:"Open"}, "Action added.").catch(e=>pstatus(e.message,true));
document.getElementById("createSchedule").onclick = () => createRecord("schedule", {name:scheduleName.value, frequency:scheduleFrequency.value, format:"PDF", status:"Active"}, "Report schedule saved. The local MVP stores schedules; attach a mail worker for unattended delivery.").catch(e=>pstatus(e.message,true));

document.getElementById("evaluateAlerts").onclick = async () => { try { const rows=await api("/api/platform/alerts/evaluate",{method:"POST"}); platformState.alertEvaluation=Object.fromEntries(rows.map(r=>[r.id,r])); renderAlerts(platformState.bootstrap.alerts); bindDynamicActions(); pstatus(`${rows.filter(r=>r.triggered).length} alert(s) triggered.`); } catch(e){pstatus(e.message,true);} };

["volumeChange","priceChange","costChange","discountChange"].forEach(id => document.getElementById(id).oninput = e => document.getElementById(id.replace("Change","Value")).value = `${e.target.value}%`);
document.getElementById("runScenario").onclick = async () => { try { const input={volumeChange:+volumeChange.value,priceChange:+priceChange.value,costChange:+costChange.value,discountChange:+discountChange.value,regions:state.selectedRegions,categories:state.selectedCategories}; const d=await api("/api/platform/scenario",jsonOptions("POST",input)); const fmt=v=>`$${Math.round(v).toLocaleString()}`; scenarioResults.innerHTML=[["Projected sales",fmt(d.projected.sales)],["Projected profit",fmt(d.projected.profit)],["Projected margin",`${(d.projected.margin*100).toFixed(1)}%`]].map(([l,v])=>`<article class="metric"><div class="metric-label">${l}</div><div class="metric-value">${v}</div></article>`).join(""); Plotly.newPlot("scenarioChart",[{type:"bar",x:["Sales","Profit"],y:[d.baseline.sales,d.baseline.profit],name:"Baseline"},{type:"bar",x:["Sales","Profit"],y:[d.projected.sales,d.projected.profit],name:"Scenario"}],chartLayout("Baseline vs scenario"),{displayModeBar:false,responsive:true}); pstatus("Scenario calculated."); } catch(e){pstatus(e.message,true);} };
document.getElementById("runBacktest").onclick = async () => { try { const d=await api("/api/platform/forecast-diagnostics"); backtestSummary.innerHTML=[["Status",d.status],["Accuracy",d.accuracy==null?"N/A":`${d.accuracy}%`],["MAPE",d.mape==null?"N/A":`${d.mape}%`],["Mean abs. error",d.mae==null?"N/A":`$${Number(d.mae).toLocaleString()}`]].map(([l,v])=>`<article class="card"><div class="metric-label">${l}</div><div class="metric-value">${v}</div></article>`).join(""); if(d.labels?.length) Plotly.newPlot("backtestChart",[{type:"scatter",mode:"lines+markers",name:"Actual",x:d.labels,y:d.actual},{type:"scatter",mode:"lines+markers",name:"Predicted",x:d.labels,y:d.predicted}],chartLayout(d.method),{displayModeBar:false,responsive:true}); } catch(e){pstatus(e.message,true);} };
document.getElementById("buildChart").onclick = async () => { try { const d=await api("/api/platform/chart",jsonOptions("POST",{prompt:chartPrompt.value,regions:state.selectedRegions,categories:state.selectedCategories})); const trace=d.type==="pie"?{type:"pie",labels:d.labels,values:d.values}:{type:d.type,x:d.labels,y:d.values,mode:d.type==="line"?"lines+markers":undefined}; Plotly.newPlot("customChart",[trace],chartLayout(d.title),{displayModeBar:false,responsive:true}); chartExplanation.textContent=d.explanation; await refreshPlatform("Chart generated and added to history."); } catch(e){pstatus(e.message,true);} };
document.getElementById("cleanDataset").onclick = async () => { try { const d=await api("/api/platform/clean",jsonOptions("POST",{removeDuplicates:removeDuplicates.checked,fillNumeric:fillNumeric.checked})); render(d); cleaningResult.textContent=`${d.cleaningSummary.duplicatesRemoved} duplicates removed; ${d.cleaningSummary.rowsAfter} rows remain.`; await refreshPlatform("Cleaning rules applied."); } catch(e){pstatus(e.message,true);} };
document.getElementById("connectDatabase").onclick = async () => { try { const d=await api("/api/platform/connect",jsonOptions("POST",{type:"sqlite",database:databasePath.value,table:databaseTable.value})); render(d); await refreshPlatform("Database connected and analyzed."); } catch(e){pstatus(e.message,true);} };
async function saveMetrics(){ await api("/api/platform/metrics",jsonOptions("PUT",platformState.metrics)); await refreshPlatform("Semantic metrics saved."); }
document.getElementById("addMetric").onclick = async () => { if(!metricName.value.trim()||!metricFormula.value.trim()) return pstatus("Metric name and formula are required.",true); platformState.metrics.push({name:metricName.value.trim(),formula:metricFormula.value.trim(),format:metricFormat.value}); await saveMetrics(); };

refreshPlatform().catch(e=>pstatus(e.message,true));
