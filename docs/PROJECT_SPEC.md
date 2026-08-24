# AURA-BI — Autonomous Unified Reasoning & Analytics for Business Intelligence

## Persistence

MongoDB through PyMongo is the production persistence target. Workspace is the ownership boundary for datasets and their analytical artifacts. Legacy SQLite is retained only as an explicit import source; source files and model artifacts remain external references.

**Research position:** *AURA-BI: A Self-Adaptive Multi-Agent Framework for Autonomous Business Intelligence over Heterogeneous Enterprise Data.*

## Problem and questions

Traditional BI requires manual schema interpretation, KPI construction, chart configuration, modelling and interpretation. AURA-BI studies whether a self-adaptive architecture can understand unfamiliar enterprise datasets, select appropriate analytics/ML, compute verified evidence, and produce useful BI with minimal configuration.

RQ1 schema-role accuracy; RQ2 analytical-task selection versus manual workflows; RQ3 evidence grounding and unsupported numerical claims; RQ4 adaptive visualization relevance; RQ5 multi-stage anomaly/root-cause ranking; RQ6 automatic model selection and predictive performance.

## Contributions

1. Semantic Business Schema Engine
2. Adaptive Analytics Planner
3. Automatic KPI and visualization discovery
4. Autonomous ML task/model selection
5. Evidence-grounded analytics narratives
6. Multi-stage anomaly/root-cause investigation
7. AURABench heterogeneous-business benchmark

## Scope and guardrails

AURA-BI performs autonomous analytics, not causal decision intelligence. Correlation, contribution analysis, and SHAP are explicitly non-causal. Numerical claims must come from `AnalyticsEvidence`; unanswerable questions return `INSUFFICIENT DATA`; source data is preserved; model metrics require actual runs. This differs from NEXORA-CDI, which studies causal inference, treatment effects, counterfactual decisions, calibrated decision confidence, decision gates, and decision provenance.

## Architecture

`data → semantic → analytics/visualization/ml/anomaly → evidence → provider-backed explanation`. Specialized Data, Analyst, ML, Anomaly, Visualization and Report services exchange structured Python dataclasses; the Orchestrator selects deterministic work first. A provider abstraction may use Gemini only to phrase computed evidence and may never replace computation.

## Phase 2 product workflows

The existing Flask/vanilla-JS UI exposes Data Intelligence (profile, role corrections, KPIs), Analytics (structured execution and evidence), AutoML (target-confirmed training and run history), Anomaly Intelligence (latest-period contribution decomposition), AI Analyst (plan/evidence details), Reports (evidence register), and Research (accurately scoped benchmark status).

## Evaluation

AURABench uses synthetic retail, e-commerce, inventory, marketing, finance, and churn families with role/KPI/task/anomaly ground truth. Metrics include role accuracy/macro-F1, task accuracy, KPI precision/recall/F1, numerical correctness/unsupported-claim rate/answerability, model performance, anomaly F1/root-cause ranking, and chart-selection accuracy. Baselines: B0 static/manual, B1 direct LLM context, B2 semantics without planner, B3 full AURA-BI, plus component ablations.
