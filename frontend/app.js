const state = {
  regions: [],
  categories: [],
  selectedRegions: [],
  selectedCategories: [],
  lastAnswer: "",
  recognition: null,
  listening: false,
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

  plotBar("categoryChart", "Sales by Category", payload.charts.categorySales.labels, payload.charts.categorySales.values);
  plotBar("regionChart", "Profit by Region", payload.charts.regionProfit.labels, payload.charts.regionProfit.values);
  plotBar("marginChart", "Margin by Category", payload.charts.marginByCategory.labels, payload.charts.marginByCategory.values);
  plotBar("discountChart", "Average Discount by Category", payload.charts.discountByCategory.labels, payload.charts.discountByCategory.values);
  plotLine("monthlyChart", "Monthly Sales Trend", payload.charts.monthlySales.labels, payload.charts.monthlySales.values);
  plotForecast(payload.charts.forecast);
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

if (!browserSupportsVoiceInput()) {
  setVoiceStatus("Voice playback works here, but voice questions need Chrome or Edge support.", true);
}

document.querySelectorAll("nav a").forEach((link) => {
  link.addEventListener("click", () => {
    document.querySelectorAll("nav a").forEach((item) => item.classList.remove("active"));
    link.classList.add("active");
  });
});

resetAnalysisOnFreshPage().catch((error) => {
  document.getElementById("sourceLabel").textContent = error.message;
});
