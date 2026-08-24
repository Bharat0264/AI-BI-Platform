from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON
from .database import Base

def utcnow(): return datetime.now(timezone.utc)

class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ready", nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class DatasetProfile(Base):
    __tablename__ = "dataset_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), unique=True)
    profile: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class SemanticColumn(Base):
    __tablename__ = "semantic_columns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    physical_type: Mapped[str] = mapped_column(String(80), nullable=False)
    semantic_role: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    user_corrected_role: Mapped[str | None] = mapped_column(String(80))
    correction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("dataset_id", "column_name", name="uq_semantic_column"),)

class AnalyticsRun(Base):
    __tablename__ = "analytics_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="RESTRICT"), index=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(80), nullable=False)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_metadata: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class Evidence(Base):
    __tablename__ = "analytics_evidence"
    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="RESTRICT"), index=True)
    analysis_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_columns: Mapped[list] = mapped_column(JSON, nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    uncertainty: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class MLRun(Base):
    __tablename__ = "ml_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="RESTRICT"), index=True)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    feature_importance: Mapped[dict] = mapped_column(JSON, nullable=False)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifact_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class AnomalyInvestigation(Base):
    __tablename__ = "anomaly_investigations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="RESTRICT"), index=True)
    metric: Mapped[str | None] = mapped_column(String(255))
    comparison: Mapped[dict] = mapped_column(JSON, nullable=False)
    contributors: Mapped[list] = mapped_column(JSON, nullable=False)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("analytics_evidence.evidence_id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class AIQuery(Base):
    __tablename__ = "ai_queries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="RESTRICT"), index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    interpreted_task: Mapped[str] = mapped_column(String(100), nullable=False)
    answerability: Mapped[str] = mapped_column(String(40), nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="RESTRICT"), index=True)
    evidence_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

# Legacy API compatibility; these tables pre-date AURA’s normalized entities.
class LegacyRecord(Base):
    __tablename__ = "records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[object] = mapped_column(JSON, nullable=False)
