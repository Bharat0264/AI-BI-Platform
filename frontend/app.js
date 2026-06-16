const state = {
  regions: [],
  categories: [],
  selectedRegions: [],
  selectedCategories: [],
};

const colors = ["#14b8a6", "#f97316", "#7c3aed", "#0ea5e9", "#ef4444", "#84cc16"];

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
    `<option value="${value}" ${selected.includes(value) ? "selected" : ""}>${value}</option>`
  )).join("");
}

function selectedValues(element) {
  return Array.from(element.selectedOptions).map((option) => option.value);
}

function renderMetrics(metrics) {
  document.getElementById("metrics").innerHTML = metrics.length ? metrics.map((item) => `
    <article class="metric">
      <div class="metric-label">${item.label}</div>
      <div class="metric-value">${item.value}</div>
      <div class="metric-note">${item.note}</div>
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
    <article class="card"><div class="metric-label">${label}</div><div class="metric-value">${value}</div></article>
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
    <thead><tr>${columns.map((column) => `<th>${column}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((row) => `<tr>${columns.map((column) => `<td>${row[column] ?? ""}</td>`).join("")}</tr>`).join("")}</tbody>
  `;
}

function renderCards(id, cards) {
  document.getElementById(id).innerHTML = cards.length ? cards.map((item) => `
    <article class="card"><h3>${item.title}</h3><p>${item.body}</p></article>
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
  renderQuality(payload.quality);
  renderCards("insightCards", payload.insights);
  renderCards("anomalyCards", payload.anomalies);
  renderTable("previewTable", payload.preview);
  renderTable("forecastTable", payload.forecastTable);

  plotBar("categoryChart", "Sales by Category", payload.charts.categorySales.labels, payload.charts.categorySales.values);
  plotBar("regionChart", "Profit by Region", payload.charts.regionProfit.labels, payload.charts.regionProfit.values);
  plotLine("monthlyChart", "Monthly Sales Trend", payload.charts.monthlySales.labels, payload.charts.monthlySales.values);
  plotForecast(payload.charts.forecast);
}

async function loadAnalysis() {
  const payload = await fetchJson(`/api/analysis?${queryString()}`);
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

document.getElementById("uploadForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await uploadDataset();
});

document.getElementById("datasetFile").addEventListener("change", () => {
  const file = document.getElementById("datasetFile").files[0];
  setUploadStatus(file ? `${file.name} selected. Click Analyze CSV to import it.` : "");
});

document.getElementById("askButton").addEventListener("click", async () => {
  const question = document.getElementById("question").value.trim();
  if (!question) return;
  document.getElementById("answer").textContent = "Analyzing...";
  const payload = await fetchJson("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      regions: state.selectedRegions,
      categories: state.selectedCategories,
    }),
  });
  document.getElementById("answer").textContent = payload.answer;
});

document.querySelectorAll("nav a").forEach((link) => {
  link.addEventListener("click", () => {
    document.querySelectorAll("nav a").forEach((item) => item.classList.remove("active"));
    link.classList.add("active");
  });
});

loadAnalysis().catch((error) => {
  document.getElementById("sourceLabel").textContent = error.message;
});
