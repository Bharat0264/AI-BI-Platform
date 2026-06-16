# AI Autonomous Business Intelligence Platform

An AI-powered business intelligence web app for analyzing CSV datasets, exploring KPIs, detecting risk signals, forecasting sales, asking Gemini-powered business questions, and generating executive PDF reports.

## Features

- CSV upload and demo dataset analysis
- Executive KPI dashboard
- Interactive Plotly charts
- Region and category filters
- Data quality diagnostics
- Autonomous recommendations and anomaly detection
- Six-month ML sales forecast
- Gemini AI business assistant
- Downloadable CSV exports and PDF reports

## Tech Stack

| Technology | Purpose |
| --- | --- |
| Flask | Web application server |
| Gunicorn | Production WSGI server |
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
python app/dashboard.py
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
    startCommand: sh ./render-start.sh
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
