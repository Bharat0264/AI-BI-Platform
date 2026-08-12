# AI Business Intelligence Platform

An end-to-end business intelligence application that turns raw operational data into executive KPIs, forecasts, AI-assisted insights, and actionable business plans. The platform combines a Flask analytics API with a responsive JavaScript dashboard and supports CSV, Excel, JSON, and local SQLite data sources.

> Portfolio project by **Bharath Sai Pulipati** — built to demonstrate full-stack development, data analytics, machine learning, generative AI integration, and product-oriented decision support.

## Why This Project Matters

Business teams often move between spreadsheets, dashboards, forecasting tools, and written reports before they can make a decision. This project brings those steps into one workflow: import a dataset, validate its quality, explore performance, model future outcomes, ask questions in natural language, and track the actions that follow.

## Key Capabilities

- **Automated data onboarding:** imports CSV, Excel, and JSON files, detects business fields, and normalizes common date, revenue, profit, product, region, quantity, inventory, and transaction columns.
- **Executive analytics:** calculates KPIs, period-over-period changes, profitability, discount sensitivity, regional performance, product rankings, and margin-risk signals.
- **Interactive dashboards:** provides Plotly visualizations, region/category filters, data previews, and downloadable CSV outputs.
- **Forecasting and planning:** produces a six-month sales forecast, backtesting metrics, next-month product demand, safety-stock targets, replenishment quantities, and expected revenue/profit.
- **AI business assistant:** answers natural-language business questions with Google Gemini, supporting browser voice input, spoken responses, and evidence citations.
- **Decision Room:** includes what-if simulation, natural-language chart creation, saved dashboards, metric alerts, action tracking, scheduled-report definitions, and semantic metrics.
- **Reporting:** generates executive PDF reports and reusable chart assets.
- **Persistent workspace:** stores user profiles, workspace settings, dashboards, alerts, actions, schedules, and analysis history in SQLite.
- **Indian stock analysis:** supports NSE/BSE lookup, trend scoring, risk metrics, and Monte Carlo scenarios.

## Technical Highlights

| Area | Implementation |
| --- | --- |
| Backend | Flask REST API with modular Python analytics services |
| Frontend | Responsive HTML, CSS, and vanilla JavaScript dashboard |
| Analytics | Pandas and NumPy transformations with reusable schema mapping |
| Machine learning | Scikit-learn forecasting and model backtesting |
| Generative AI | Google Gemini integration for contextual business Q&A |
| Visualization | Interactive Plotly charts plus Matplotlib/Seaborn report assets |
| Persistence | SQLite-backed workspace state and saved decision artifacts |
| Reporting | ReportLab PDF generation and downloadable CSV exports |
| Deployment | Waitress production server and Render Blueprint configuration |

## Application Flow

```text
Business dataset
      |
      v
Schema detection and data-quality checks
      |
      v
KPI analysis, forecasting, and risk detection
      |
      +----> Interactive dashboards and exports
      +----> Gemini-powered questions and evidence
      +----> Demand, inventory, and scenario planning
      |
      v
Saved decisions, alerts, actions, and executive reports
```

## Project Structure

```text
AI-BI-Platform/
|-- app/                    # Analytics, forecasting, AI, and reporting modules
|-- data/                   # Sample datasets; runtime workspace files are ignored
|-- frontend/
|   |-- index.html          # Dashboard and Decision Room interface
|   |-- styles.css          # Responsive application styling
|   |-- app.js              # Core dashboard behavior and API integration
|   `-- platform.js         # Workspace and decision-management features
|-- outputs/                # Generated charts and reports
|-- platform_store.py       # SQLite persistence layer
|-- server.py               # Flask routes and application orchestration
|-- start.py                # Production entry point
|-- render.yaml             # Render deployment blueprint
`-- requirements.txt
```

## Run Locally

### Prerequisites

- Python 3.10 or newer
- A Google Gemini API key (optional; required only for AI-generated answers)

### Installation

```bash
git clone https://github.com/Bharat0264/AI-BI-Platform.git
cd AI-BI-Platform
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_api_key_here
```

Start the application:

```bash
python server.py
```

Open `http://127.0.0.1:5000` and load one of the sample datasets from `data/`, or upload your own file.

## Example Questions

- Which region has the lowest profit margin?
- What factors are contributing to declining profit?
- Which product categories should receive more inventory next month?
- How would a 10% increase in volume and a 5% increase in cost affect profit?
- What are the strongest growth opportunities in this dataset?

## Deployment

The repository includes a Render Blueprint in `render.yaml`.

1. Create a new **Blueprint** in Render.
2. Connect this GitHub repository.
3. Apply the detected service configuration.
4. Add `GEMINI_API_KEY` as an environment variable.
5. Deploy the service.

The production process uses Waitress through `python start.py`.

## Resume-Ready Description

**AI Business Intelligence Platform | Python, Flask, Pandas, Scikit-learn, Gemini, Plotly, SQLite**

- Built a full-stack BI platform that converts multi-format business datasets into executive KPIs, interactive dashboards, profitability insights, forecasts, and downloadable reports.
- Developed semantic schema detection, data-quality checks, product-demand forecasting, safety-stock recommendations, what-if modeling, and forecast backtesting using Python analytics and machine-learning libraries.
- Integrated Gemini-powered natural-language analysis with evidence citations and created a persistent decision workspace for dashboards, alerts, actions, report schedules, and business metrics.

## Responsible Use

Forecasts, stock scenarios, and AI-generated recommendations are decision-support outputs rather than financial advice. Results should be validated against source data and business context before operational use.

## Author

**Bharath Sai Pulipati**

- GitHub: [Bharat0264](https://github.com/Bharat0264)
