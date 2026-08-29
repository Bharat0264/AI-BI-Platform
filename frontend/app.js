const state = {
  regions: [],
  categories: [],
  selectedRegions: [],
  selectedCategories: [],
  lastAnswer: "",
  recognition: null,
  listening: false,
  assetType: "stocks",
};

const colors = ["#14b8a6", "#f97316", "#7c3aed", "#0ea5e9", "#ef4444", "#84cc16"];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function tokenClass(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function queryString() {
  const params = new URLSearchParams();
  state.selectedRegions.forEach((region) => params.append("region", region));
  state.selectedCategories.forEach((category) => params.append("category", category));
  return params.toString();
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Request failed");
  return payload;
}

function setUploadStatus(message, isError = false) {
  const status = document.getElementById("uploadStatus");
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function fillSelect(element, values, selected) {
  element.innerHTML = values.map((value) => (
    `<option value="${escapeHtml(value)}" ${selected.includes(value) ? "selected" : ""}>${escapeHtml(value)}</option>`
  )).join("");
}

function selectedValues(element) {
  return Array.from(element.selectedOptions).map((option) => option.value);
}

function setVoiceStatus(message, isError = false) {
  const status = document.getElementById("voiceStatus");
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function getSpeechRecognition() {
  return window.SpeechRecognition || window.webkitSpeechRecognition;
}

function browserSupportsVoiceInput() {
  return Boolean(getSpeechRecognition());
}

function browserSupportsVoiceOutput() {
  return "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

function stopSpeaking() {
  if (browserSupportsVoiceOutput()) {
    window.speechSynthesis.cancel();
  }
}

function splitSpeechText(text) {
  const cleanText = String(text || "").replace(/\s+/g, " ").trim();
  if (!cleanText) return [];

  const sentences = cleanText.match(/[^.!?]+[.!?]*/g) || [cleanText];
  const chunks = [];
  let current = "";

  sentences.forEach((sentence) => {
    const next = `${current} ${sentence}`.trim();
    if (next.length > 220 && current) {
      chunks.push(current);
      current = sentence.trim();
    } else {
      current = next;
    }
  });

  if (current) chunks.push(current);
  return chunks;
}

function playSpeechChunks(chunks, index = 0) {
  if (index >= chunks.length) {
    setVoiceStatus("Voice assistant ready.");
    return;
  }

  const utterance = new SpeechSynthesisUtterance(chunks[index]);
  utterance.rate = 0.95;
  utterance.pitch = 1;
  utterance.volume = 1;
  utterance.onstart = () => setVoiceStatus(`Playing answer ${index + 1}/${chunks.length}...`);
  utterance.onend = () => playSpeechChunks(chunks, index + 1);
  utterance.onerror = (event) => {
    if (event.error === "canceled" || event.error === "interrupted") {
      setVoiceStatus("Voice stopped.");
      return;
    }
    setVoiceStatus(`Voice playback failed: ${event.error || "unknown error"}. Try Play Answer again.`, true);
  };
  window.speechSynthesis.speak(utterance);
}

function speakText(text) {
  if (!browserSupportsVoiceOutput()) {
    setVoiceStatus("Voice playback is not supported in this browser.", true);
    return;
  }

  const chunks = splitSpeechText(text);
  if (!chunks.length) {
    setVoiceStatus("There is no answer to play yet.", true);
    return;
  }

  stopSpeaking();
  window.setTimeout(() => playSpeechChunks(chunks), 120);
}

function renderMetrics(metrics) {
  document.getElementById("metrics").innerHTML = metrics.length ? metrics.map((item) => `
    <article class="metric ${escapeHtml(item.tone || "neutral")}">
      <div class="metric-label">${escapeHtml(item.label)}</div>
      <div class="metric-value">${escapeHtml(item.value)}</div>
      <div class="metric-note">${escapeHtml(item.note)}</div>
    </article>
  `).join("") : "";
}

function plotBar(id, title, labels, values) {
  Plotly.newPlot(id, [{
    type: "bar",
    x: labels,
    y: values,
    marker: { color: colors },
  }], chartLayout(title), { displayModeBar: false, responsive: true });
}

function plotLine(id, title, labels, values) {
  Plotly.newPlot(id, [{
    type: "scatter",
    mode: "lines+markers",
    x: labels,
    y: values,
    line: { color: "#14b8a6", width: 3 },
  }], chartLayout(title), { displayModeBar: false, responsive: true });
}

function plotForecast(data) {
  const traces = [{
    type: "scatter",
    mode: "lines+markers",
    name: "History",
    x: data.historyLabels,
    y: data.historyValues,
    line: { color: "#0ea5e9", width: 3 },
  }];

  if (data.labels.length) {
    traces.push({
      type: "scatter",
      mode: "lines+markers",
      name: "Forecast",
      x: data.labels,
      y: data.values,
      line: { color: "#f97316", width: 3 },
    });
    traces.push({
      type: "scatter",
      mode: "lines",
      name: "Upper",
      x: data.labels,
      y: data.upper,
      line: { width: 0 },
      showlegend: false,
    });
    traces.push({
      type: "scatter",
      mode: "lines",
      name: "Lower",
      x: data.labels,
      y: data.lower,
      fill: "tonexty",
      fillcolor: "rgba(249,115,22,.14)",
      line: { width: 0 },
      showlegend: false,
    });
  }

  Plotly.newPlot("forecastChart", traces, chartLayout("Sales Forecast"), { displayModeBar: false, responsive: true });
}

function chartLayout(title) {
  return {
    title,
    height: 380,
    margin: { l: 42, r: 18, t: 48, b: 42 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(255,255,255,0)",
    font: { family: "Inter, Segoe UI, Arial", color: "#101828" },
  };
}

function renderExecutiveSummary(items) {
  document.getElementById("executiveSummary").innerHTML = items.length ? items.map((item) => `
    <article class="summary-item">
      <div class="summary-label">${escapeHtml(item.label)}</div>
      <strong>${escapeHtml(item.value)}</strong>
      <p>${escapeHtml(item.detail)}</p>
    </article>
  `).join("") : `<article class="summary-item"><strong>No analysis yet</strong><p>Import a CSV to generate an executive summary.</p></article>`;
}

function renderDatasetProfile(profile) {
  const rows = [
    ["Date Range", profile.dateRange],
    ["Records Analyzed", profile.recordsAnalyzed],
    ["Total Records", profile.totalRecords],
    ["Columns", profile.columns],
    ["Numeric Columns", profile.numericColumns],
    ["Regions", profile.regions],
    ["Categories", profile.categories],
    ["Customers", profile.customers],
    ["Products", profile.products],
  ];

  document.getElementById("datasetProfile").innerHTML = rows.map(([label, value]) => `
    <div class="profile-item">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value ?? "N/A")}</strong>
    </div>
  `).join("");
}

function renderRiskOverview(risk) {
  const levers = risk.levers || [];
  document.getElementById("riskOverview").innerHTML = `
    <div class="risk-ring ${escapeHtml((risk.level || "low").toLowerCase())}">
      <span>${escapeHtml(risk.score ?? "N/A")}</span>
      <small>${escapeHtml(risk.level || "No data")} risk</small>
    </div>
    <div class="risk-details">
      <div><span>Margin</span><strong>${escapeHtml(risk.margin || "N/A")}</strong></div>
      <div><span>Loss Rate</span><strong>${escapeHtml(risk.lossRate || "N/A")}</strong></div>
      <div><span>Avg Discount</span><strong>${escapeHtml(risk.avgDiscount || "N/A")}</strong></div>
    </div>
    <div class="lever-list">
      ${levers.map((lever) => `
        <div class="lever">
          <span>${escapeHtml(lever.label)}</span>
          <strong>${escapeHtml(lever.impact)}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function renderQuality(quality) {
  const cards = [
    ["Score", quality.score],
    ["Rows", quality.rows],
    ["Clean Rows", quality.cleanRows],
    ["Columns", quality.columns],
    ["Missing Cells", quality.missingCells],
    ["Duplicate Rows", quality.duplicateRows],
    ["Invalid Dates", quality.invalidDates],
    ["Missing Required", quality.missingRequired.length ? quality.missingRequired.join(", ") : "None"],
  ];
  document.getElementById("qualityCards").innerHTML = cards.map(([label, value]) => `
    <article class="card"><div class="metric-label">${escapeHtml(label)}</div><div class="metric-value">${escapeHtml(value)}</div></article>
  `).join("");
}

function renderTable(id, rows) {
  const table = document.getElementById(id);
  if (!rows.length) {
    table.innerHTML = "<tbody><tr><td>No rows available</td></tr></tbody>";
    return;
  }
  const columns = Object.keys(rows[0]);
  table.innerHTML = `
    <thead><tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((row) => `<tr>${columns.map((column) => `<td>${escapeHtml(row[column] ?? "")}</td>`).join("")}</tr>`).join("")}</tbody>
  `;
}

function renderCards(id, cards) {
  document.getElementById(id).innerHTML = cards.length ? cards.map((item) => `
    <article class="card ${tokenClass(item.severity || item.type || "")}">
      <div class="card-kicker">${escapeHtml(item.severity || item.type || "Signal")}</div>
      <h3>${escapeHtml(item.title)}</h3>
      <p>${escapeHtml(item.body)}</p>
    </article>
  `).join("") : `<article class="card"><h3>No CSV imported</h3><p>Import a CSV to generate this analysis.</p></article>`;
}

function renderDemandPlan(plan = {}) {
  const totals = plan.totals || {};
  document.getElementById("demandMonth").textContent = totals.forecastMonth ? `Forecast: ${totals.forecastMonth}` : "Load data to forecast";
  const values = [
    ["Predicted units", Number(totals.predictedUnits || 0).toLocaleString()],
    ["Stock to add", Number(totals.stockToAdd || 0).toLocaleString()],
    ["Expected revenue", `$${Number(totals.predictedRevenue || 0).toLocaleString()}`],
    ["Expected profit", `$${Number(totals.predictedProfit || 0).toLocaleString()}`],
  ];
  document.getElementById("demandMetrics").innerHTML = values.map(([label,value]) => `<article class="metric"><div class="metric-label">${escapeHtml(label)}</div><div class="metric-value">${escapeHtml(value)}</div></article>`).join("");
  const notice = document.getElementById("demandNotice");
  notice.hidden = !plan.quantityIsEstimated;
  notice.textContent = plan.quantityIsEstimated ? "No quantity/units column was found. Unit demand currently treats each transaction row as one unit. Upload quantity and optional inventory/stock columns for precise replenishment recommendations." : "";
  const products = plan.products || [];
  const priority = products.filter(item => item.action === "Increase production").slice(0, 6);
  document.getElementById("productionRecommendations").innerHTML = priority.length ? priority.map(item => `<article class="card growth-bet"><div class="card-kicker">${escapeHtml(item.sector)} · ${escapeHtml(item.confidence)}% confidence</div><h3>${escapeHtml(item.product)}</h3><p>Add <strong>${Number(item.stockToAdd).toLocaleString()} units</strong> for ${escapeHtml(item.forecastMonth)}. Expected demand is ${Number(item.predictedUnits).toLocaleString()} units, producing about $${Number(item.predictedRevenue).toLocaleString()} revenue and $${Number(item.predictedProfit).toLocaleString()} profit.</p></article>`).join("") : `<article class="card"><p>No product currently shows a strong production-increase signal.</p></article>`;
  renderTable("demandProductTable", products.map(item => ({Product:item.product,Sector:item.sector,Action:item.action,"Predicted units":item.predictedUnits,"Safety stock":item.safetyStock,"Stock to add":item.stockToAdd,"Expected revenue":`$${Number(item.predictedRevenue).toLocaleString()}`,"Expected profit":`$${Number(item.predictedProfit).toLocaleString()}`,Growth:`${item.growthRate}%`,Confidence:`${item.confidence}%`})));
  renderTable("demandSectorTable", (plan.sectors || []).map(item => ({Sector:item.sector,"Stock to add":item.stockToAdd,"Expected revenue":`$${Number(item.predictedRevenue).toLocaleString()}`,"Expected profit":`$${Number(item.predictedProfit).toLocaleString()}`,Growth:`${item.growthRate}%`,Recommendation:item.growthRate >= 3 ? "Increase production" : item.growthRate <= -8 ? "Reduce production" : "Maintain"})));
}

function render(payload) {
  state.regions = payload.regions;
  state.categories = payload.categories;
  state.selectedRegions = payload.selectedRegions;
  state.selectedCategories = payload.selectedCategories;

  fillSelect(document.getElementById("regionFilter"), state.regions, state.selectedRegions);
  fillSelect(document.getElementById("categoryFilter"), state.categories, state.selectedCategories);
  document.getElementById("sourceLabel").textContent = `${payload.source} | ${payload.rows.toLocaleString()} rows`;

  renderMetrics(payload.metrics);
  renderExecutiveSummary(payload.executiveSummary || []);
  renderDatasetProfile(payload.datasetProfile || {});
  renderRiskOverview(payload.riskOverview || {});
  renderQuality(payload.quality);
  renderCards("insightCards", payload.insights);
  renderCards("anomalyCards", payload.anomalies);
  renderCards("opportunityCards", payload.opportunities || []);
  renderTable("segmentTable", payload.segmentTable || []);
  renderTable("productTable", payload.productTable || []);
  renderTable("marginMatrixTable", payload.marginMatrix || []);
  renderTable("discountSensitivityTable", payload.discountSensitivity || []);
  renderTable("previewTable", payload.preview);
  renderTable("forecastTable", payload.forecastTable);
  renderDemandPlan(payload.demandPlan);

  plotBar("categoryChart", "Sales by Category", payload.charts.categorySales.labels, payload.charts.categorySales.values);
  plotBar("regionChart", "Profit by Region", payload.charts.regionProfit.labels, payload.charts.regionProfit.values);
  plotBar("marginChart", "Margin by Category", payload.charts.marginByCategory.labels, payload.charts.marginByCategory.values);
  plotBar("discountChart", "Average Discount by Category", payload.charts.discountByCategory.labels, payload.charts.discountByCategory.values);
  plotLine("monthlyChart", "Monthly Sales Trend", payload.charts.monthlySales.labels, payload.charts.monthlySales.values);
  plotForecast(payload.charts.forecast);
  loadAuraIntelligence().catch(() => {});
}

async function loadAnalysis() {
  const payload = await fetchJson(`/api/analysis?${queryString()}`);
  render(payload);
}

async function resetAnalysisOnFreshPage() {
  state.regions = [];
  state.categories = [];
  state.selectedRegions = [];
  state.selectedCategories = [];
  state.lastAnswer = "";
  document.getElementById("question").value = "";
  document.getElementById("answer").textContent = "";
  setUploadStatus("");
  const payload = await fetchJson("/api/reset", { method: "POST" });
  render(payload);
}

document.getElementById("filterForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  state.selectedRegions = selectedValues(document.getElementById("regionFilter"));
  state.selectedCategories = selectedValues(document.getElementById("categoryFilter"));
  await loadAnalysis();
});

document.getElementById("resetFilters").addEventListener("click", async () => {
  state.selectedRegions = [];
  state.selectedCategories = [];
  await loadAnalysis();
});

async function uploadDataset() {
  const fileInput = document.getElementById("datasetFile");
  const button = document.getElementById("analyzeCsvButton");
  const file = fileInput.files[0];
  if (!file) {
    setUploadStatus("Choose a CSV file to analyze.", true);
    fileInput.click();
    return;
  }

  setUploadStatus(`Analyzing ${file.name}...`);
  button.disabled = true;
  const formData = new FormData();
  formData.append("dataset", file);
  try {
    const payload = await fetchJson("/api/upload", { method: "POST", body: formData });
    render(payload);
    setUploadStatus(`Imported ${payload.source} with ${payload.rows.toLocaleString()} rows.`);
  } catch (error) {
    setUploadStatus(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function loadDemoDataset() {
  const button = document.getElementById("demoButton");
  setUploadStatus("Loading demo dataset...");
  button.disabled = true;
  try {
    const payload = await fetchJson("/api/demo", { method: "POST" });
    render(payload);
    setUploadStatus(`Loaded ${payload.source} with ${payload.rows.toLocaleString()} rows.`);
  } catch (error) {
    setUploadStatus(error.message, true);
  } finally {
    button.disabled = false;
  }
}

document.getElementById("uploadForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await uploadDataset();
});

document.getElementById("demoButton").addEventListener("click", loadDemoDataset);

document.getElementById("datasetFile").addEventListener("change", () => {
  const file = document.getElementById("datasetFile").files[0];
  setUploadStatus(file ? `${file.name} selected. Click Analyze CSV to import it.` : "");
});

async function askBusinessQuestion({ speak = true } = {}) {
  const question = document.getElementById("question").value.trim();
  if (!question) {
    setVoiceStatus("Type or speak a business question first.", true);
    return;
  }

  document.getElementById("answer").textContent = "Analyzing...";
  setVoiceStatus("Asking AI analyst...");

  try {
    const payload = await fetchJson("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        regions: state.selectedRegions,
        categories: state.selectedCategories,
      }),
    });
    state.lastAnswer = payload.answer;
    document.getElementById("answer").textContent = payload.answer;
    const citations = payload.citations || [];
    document.getElementById("answerCitations").innerHTML = citations.map(item => `<article><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong><small>${escapeHtml(item.source)}</small></article>`).join("");
    document.getElementById("aiEvidenceDetail").textContent = JSON.stringify({ plan: payload.plan, evidence: payload.evidence }, null, 2);
    setVoiceStatus(speak ? "AI answer ready. Playing response..." : "AI answer ready.");
    if (speak) speakText(payload.answer);
  } catch (error) {
    state.lastAnswer = "";
    document.getElementById("answer").textContent = error.message;
    setVoiceStatus(error.message, true);
  }
}

function startVoiceQuestion() {
  if (!browserSupportsVoiceInput()) {
    setVoiceStatus("Voice questions are not supported in this browser. Try Chrome or Edge.", true);
    return;
  }

  if (state.listening && state.recognition) {
    state.recognition.stop();
    return;
  }

  const Recognition = getSpeechRecognition();
  const recognition = new Recognition();
  recognition.lang = "en-US";
  recognition.interimResults = true;
  recognition.continuous = false;
  state.recognition = recognition;
  state.listening = true;

  const button = document.getElementById("voiceQuestionButton");
  button.textContent = "Listening...";
  button.classList.add("listening");
  setVoiceStatus("Listening. Ask your business question.");

  recognition.onresult = (event) => {
    const transcript = Array.from(event.results)
      .map((result) => result[0].transcript)
      .join(" ")
      .trim();
    document.getElementById("question").value = transcript;
  };

  recognition.onerror = (event) => {
    setVoiceStatus(`Voice input failed: ${event.error}`, true);
  };

  recognition.onend = () => {
    state.listening = false;
    button.textContent = "Start Voice Question";
    button.classList.remove("listening");
    const question = document.getElementById("question").value.trim();
    if (question) {
      setVoiceStatus("Voice question captured. Sending to AI...");
      askBusinessQuestion({ speak: true });
    } else {
      setVoiceStatus("No voice question was detected.", true);
    }
  };

  recognition.start();
}

document.getElementById("askButton").addEventListener("click", () => {
  askBusinessQuestion({ speak: true });
});

document.getElementById("voiceQuestionButton").addEventListener("click", startVoiceQuestion);

document.getElementById("speakAnswerButton").addEventListener("click", () => {
  speakText(state.lastAnswer || document.getElementById("answer").textContent);
});

document.getElementById("stopVoiceButton").addEventListener("click", () => {
  if (state.recognition && state.listening) state.recognition.stop();
  stopSpeaking();
  setVoiceStatus("Voice stopped.");
});

document.getElementById("stockForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const company = document.getElementById("stockCompany").value.trim();
  const button = document.getElementById("stockAnalyzeButton");
  const status = document.getElementById("stockStatus");
  button.disabled = true;
  status.textContent = `Fetching recent market data for ${company}...`;
  status.classList.remove("error");
  try {
    const data = await fetchJson("/api/stocks/analyze", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({company, assetType:state.assetType})});
    document.getElementById("stockResults").hidden = false;
    document.getElementById("stockHeader").innerHTML = `<div><h3>${escapeHtml(data.company)}</h3><span>${escapeHtml(data.symbol)} · ${escapeHtml(data.exchange)} · As of ${escapeHtml(data.asOf)}</span></div><div class="stock-score"><strong>${escapeHtml(data.score)}/100</strong><span>${escapeHtml(data.stance)}</span></div>`;
    const metrics = [["Latest price",`${data.currency} ${Number(data.price).toLocaleString()}`],["1 month",`${data.returns.oneMonth}%`],["3 months",`${data.returns.threeMonths}%`],["1 year",`${data.returns.oneYear}%`],["Volatility",`${data.technicals.annualizedVolatility}%`],["52-week range",`${data.fiftyTwoWeekLow} – ${data.fiftyTwoWeekHigh}`]];
    document.getElementById("stockMetrics").innerHTML = metrics.map(([l,v]) => `<article class="metric"><div class="metric-label">${escapeHtml(l)}</div><div class="metric-value">${escapeHtml(v)}</div></article>`).join("");
    Plotly.newPlot("stockChart", [{type:"scatter",mode:"lines",x:data.chart.dates,y:data.chart.prices,line:{color:"#14b8a6",width:3}}], chartLayout(`${data.symbol} recent price history`), {displayModeBar:false,responsive:true});
    renderTable("stockForecastTable", data.forecasts.map(f => ({Horizon:f.horizon,"Median scenario":f.median,"10th percentile":f.low,"90th percentile":f.high,"Probability above current":`${f.positiveProbability}%`})));
    document.getElementById("stockSignals").innerHTML = data.signals.map((s,i) => `<article class="card"><div class="card-kicker">Signal ${i+1}</div><p>${escapeHtml(s)}</p></article>`).join("") + `<article class="card"><div class="card-kicker">Method</div><p>${escapeHtml(data.methodology)}</p></article>`;
    document.getElementById("stockDisclaimer").textContent = data.disclaimer;
    status.textContent = "Analysis complete. Scenarios are uncertainty ranges, not guarantees.";
  } catch (error) {
    status.textContent = error.message;
    status.classList.add("error");
  } finally {
    button.disabled = false;
  }
});

document.querySelectorAll("#assetTabs button").forEach((tab) => {
  tab.addEventListener("click", () => {
    state.assetType = tab.dataset.asset;
    document.querySelectorAll("#assetTabs button").forEach((item) => item.classList.toggle("active", item === tab));
    const labels = {stocks:"stock symbol or company",etfs:"ETF symbol or name",mutualfunds:"mutual fund name",bonds:"listed bond symbol",futures:"futures contract symbol"};
    document.getElementById("stockCompany").placeholder = `Enter ${labels[state.assetType]}`;
    document.getElementById("stockResults").hidden = true;
    document.getElementById("stockStatus").textContent = `${tab.textContent} selected.`;
  });
});

if (!browserSupportsVoiceInput()) {
  setVoiceStatus("Voice playback works here, but voice questions need Chrome or Edge support.", true);
}

function showFeaturePage(pageId, { updateHash = false } = {}) {
  const target = document.querySelector(`[data-page-content="${pageId}"]`);
  if (!target) pageId = "overview";

  document.querySelectorAll("[data-page-content]").forEach((page) => {
    page.classList.toggle("active-page", page.dataset.pageContent === pageId);
  });
  document.querySelectorAll("nav a[data-page]").forEach((link) => {
    const isActive = link.dataset.page === pageId;
    link.classList.toggle("active", isActive);
    link.setAttribute("aria-current", isActive ? "page" : "false");
  });

  if (updateHash && window.location.hash !== `#${pageId}`) {
    window.location.hash = pageId;
  }
  window.scrollTo({ top: 0, behavior: "smooth" });

  // Plotly measures hidden containers as zero-width. Resize charts after their
  // feature page becomes visible so charts remain usable when returning to it.
  window.requestAnimationFrame(() => {
    document.querySelectorAll("[data-page-content].active-page .js-plotly-plot").forEach((chart) => {
      try { Plotly.Plots.resize(chart); } catch (_) { /* chart has not rendered yet */ }
    });
  });
}

document.querySelectorAll("nav a[data-page]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    showFeaturePage(link.dataset.page, { updateHash: true });
  });
});

window.addEventListener("hashchange", () => {
  showFeaturePage(window.location.hash.slice(1) || "overview");
});

showFeaturePage(window.location.hash.slice(1) || "overview");

function fillAuraSelectors(fields) {
  const options = fields.map(f => `<option value="${escapeHtml(f.column)}">${escapeHtml(f.column)} (${escapeHtml(f.semantic_role)})</option>`).join("");
  document.getElementById("analyticsMeasure").innerHTML = `<option value="">Auto-select measure</option>${options}`;
  document.getElementById("analyticsDimension").innerHTML = `<option value="">No grouping</option>${options}`;
  document.getElementById("mlTarget").innerHTML = `<option value="">Select target</option>${options}`;
}

async function loadAuraIntelligence() {
  const data = await fetchJson("/api/aura/inspect");
  const profile = data.profile || {}; const fields = data.semantic_schema || [];
  const colProfile = profile.column_profile || {};
  const missing = Object.values(colProfile).reduce((sum, item) => sum + (item.null_percent || 0), 0);
  document.getElementById("auraDatasetOverview").innerHTML = [["Rows",profile.rows],["Columns",profile.columns],["Duplicates",profile.duplicates],["Missing %",missing.toFixed(1)]].map(([k,v]) => `<article class="card"><div class="metric-label">${k}</div><div class="metric-value">${escapeHtml(v)}</div></article>`).join("");
  const roleOptions=["identifier","date/time","revenue","profit","cost","quantity","price","customer","product","category","region","location","channel","target/outcome","generic numerical","generic categorical"];
  document.getElementById("semanticTable").innerHTML=`<thead><tr><th>Column</th><th>Detected Type</th><th>Semantic Role</th><th>Confidence</th><th>Reason</th><th>Correction</th></tr></thead><tbody>${fields.map(f=>`<tr><td>${escapeHtml(f.column)}</td><td>${escapeHtml(colProfile[f.column]?.dtype||"unknown")}</td><td>${escapeHtml(f.semantic_role)}</td><td>${Math.round(f.confidence*100)}%</td><td>${escapeHtml(f.reason)}</td><td><select data-role-column="${escapeHtml(f.column)}">${roleOptions.map(role=>`<option value="${role}" ${role===f.semantic_role?"selected":""}>${role}</option>`).join("")}</select></td></tr>`).join("")}</tbody>`;
  document.querySelectorAll("[data-role-column]").forEach(select=>select.addEventListener("change",async()=>{ try { await fetchJson("/api/aura/schema",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({corrections:{[select.dataset.roleColumn]:select.value}})}); loadAuraIntelligence(); } catch(error) { document.getElementById("auraWarnings").textContent=error.message; } }));
  document.getElementById("auraKpis").innerHTML = (data.kpis || []).map(k => `<article class="card"><div class="card-kicker">${escapeHtml(k.applicability_reason)}</div><h3>${escapeHtml(k.name)}: ${Number(k.computed_value).toLocaleString(undefined,{maximumFractionDigits:2})}</h3><p>${escapeHtml(k.formula)} · ${escapeHtml(k.source_columns.join(", "))}</p></article>`).join("") || `<p class="muted">No valid KPIs can be derived from this dataset.</p>`;
  document.getElementById("auraWarnings").textContent = (profile.quality_warnings || []).join(" · ") || "No data-quality warnings found.";
  fillAuraSelectors(fields);
  loadAuraHistory().catch(() => {});
}

async function loadAuraHistory() {
  const data = await fetchJson("/api/aura/history");
  renderTable("mlHistory", (data.ml_run || []).map(r => ({Target:r.name,Task:r.payload.task,Model:r.payload.model,Metrics:JSON.stringify(r.payload.metrics),Created:r.created_at})));
}

async function runAuraAnalytics() {
  const status=document.getElementById("analyticsStatus"); status.textContent="Computing verified analysis...";
  try {
    const data=await fetchJson("/api/aura/analytics",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({objective:document.getElementById("analyticsObjective").value || "descriptive statistics",measure:document.getElementById("analyticsMeasure").value || null,dimension:document.getElementById("analyticsDimension").value || null})});
    const r=data.evidence.result; const series=r.series || {};
    if (Object.keys(series).length) plotBar("auraAnalysisChart", `${r.measure} by ${r.dimension}`,Object.keys(series),Object.values(series));
    else Plotly.newPlot("auraAnalysisChart",[{type:"histogram",x:[r.mean],marker:{color:colors[0]}}],chartLayout(`${r.measure} summary`),{displayModeBar:false,responsive:true});
    document.getElementById("chartReason").textContent=data.visualization.reasoning;
    document.getElementById("analyticsEvidence").textContent=JSON.stringify(data.evidence,null,2); status.textContent="Analysis complete; evidence saved to workspace.";
  } catch(error) { status.textContent=error.message; status.classList.add("error"); }
}

async function trainAuraModel() {
  const status=document.getElementById("mlStatus"), target=document.getElementById("mlTarget").value;
  if (!target) { status.textContent="Select a target before training."; status.classList.add("error"); return; }
  status.textContent="Training guarded model...";
  try { const data=await fetchJson("/api/aura/ml",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({target})}); document.getElementById("mlResults").innerHTML=Object.entries(data.metrics).map(([k,v])=>`<article class="card"><div class="metric-label">${escapeHtml(k)}</div><div class="metric-value">${Number(v).toFixed(3)}</div></article>`).join("") + `<article class="card"><div class="metric-label">Model</div><div class="metric-value">${escapeHtml(data.model)}</div></article>`; status.textContent="Model run saved. Feature importance is predictive, not causal."; loadAuraHistory(); } catch(error) { status.textContent=error.message; status.classList.add("error"); }
}

async function runRootCause() {
  const status=document.getElementById("rootCauseStatus"); status.textContent="Checking the latest period and decomposing observed change...";
  try { const data=await fetchJson("/api/aura/root-cause",{method:"POST"}); status.textContent=data.answer; document.getElementById("rootCauseEvidence").textContent=JSON.stringify(data.evidence,null,2); const items=data.evidence?.result?.contributors || []; document.getElementById("rootCauseContributors").innerHTML=items.length ? items.map(x=>`<article class="card"><div class="card-kicker">${escapeHtml(x.dimension)}</div><h3>${escapeHtml(x.segment)}</h3><p>Change: ${Number(x.change).toLocaleString()} · ${Math.round(x.share_of_total_change*100)}% of observed difference</p></article>`).join("") : `<p class="muted">No ranked contributors are available for this comparison.</p>`; } catch(error) { status.textContent=error.message; status.classList.add("error"); }
}

document.getElementById("refreshAura").addEventListener("click", () => loadAuraIntelligence().catch(error => { document.getElementById("auraWarnings").textContent=error.message; }));
document.getElementById("runAnalytics").addEventListener("click", runAuraAnalytics);
document.getElementById("trainModel").addEventListener("click", trainAuraModel);
document.getElementById("runRootCause").addEventListener("click", runRootCause);

loadAnalysis().catch((error) => {
  document.getElementById("sourceLabel").textContent = error.message;
});
