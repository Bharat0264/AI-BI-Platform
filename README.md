# AI Autonomous Business Intelligence Platform

An AI-powered business intelligence website with a Flask backend API and a custom HTML/CSS/JavaScript frontend for analyzing CSV datasets, exploring executive KPIs, diagnosing profit risk, forecasting sales, asking Gemini-powered business questions, and generating executive PDF reports.

## Features

- CSV upload and demo dataset analysis
- Separate frontend and backend structure
- Executive KPI dashboard with period-over-period movement
- Interactive Plotly charts
- Region and category filters
- Data quality diagnostics
- Dataset profile, date range, customer/product coverage, and upload guardrails
- Autonomous recommendations, anomaly severity, and growth opportunity mapping
- Margin-risk matrix across region and category combinations
- Discount sensitivity analysis by discount band
- Segment and product leaderboards
- Risk score with practical profit recovery levers
- Six-month ML sales forecast
- Gemini AI business assistant with browser voice questions and spoken answers
- Downloadable CSV exports and PDF reports

## Tech Stack

| Technology | Purpose |
| --- | --- |
| Flask | Web application server |
| HTML/CSS/JavaScript | Frontend experience |
| Pandas / NumPy | Data processing |
| Plotly | Interactive charts |
| Scikit-learn | Forecasting model |
| Google Gemini API | AI analysis |
| ReportLab | PDF generation |

## Project Structure

```text
AI-BI-Platform/
├── app/
│   ├── dashboard.py
│   ├── prediction.py
│   ├── report_generator.py
│   ├── llm_engine.py
│   ├── autonomous_insights.py
│   └── ...
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── server.py
├── data/
│   └── Sample - Superstore.csv
├── outputs/
│   ├── charts/
│   └── reports/
├── render.yaml
├── requirements.txt
└── README.md
```

## Local Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
GEMINI_API_KEY=your_api_key_here
```

Run the web app:

```bash
python server.py
```

Open:

```text
http://127.0.0.1:5000
```

## Render Deployment

This repo includes `render.yaml`.

```yaml
services:
  - type: web
    name: ai-bi-platform
    runtime: python
    buildCommand: python -m pip install -r requirements.txt
    startCommand: python start.py
```

On Render:

1. Choose **New +**.
2. Choose **Blueprint**.
3. Connect this GitHub repository.
4. Apply the detected `render.yaml`.
5. Add `GEMINI_API_KEY` in the Render environment variables.
6. Deploy.

## Sample Business Questions

- Analyze business performance.
- Which region has the lowest profit?
- Suggest ways to improve revenue.
- Why are profits decreasing?
- Which category performs best?
- Predict future sales trends.

## Author

Bharath Sai Pulipati
