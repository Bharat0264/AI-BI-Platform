"""Backward-compatible workspace API backed by SQLAlchemy."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from persistence.database import get_session, init_database
from persistence.models import LegacyRecord, Setting

def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _record(row): return {"id":row.id,"kind":row.kind,"name":row.name,"payload":row.payload,"created_at":row.created_at}

def init_store():
    init_database()
    defaults={"current_user":{"name":"Bharath","role":"Admin","workspace":"Executive Workspace"},"semantic_metrics":[{"name":"Net Revenue","column":"Sales","aggregation":"sum","format":"currency"},{"name":"Gross Profit","column":"Profit","aggregation":"sum","format":"currency"},{"name":"Profit Margin","formula":"Profit / Sales","format":"percent"}]}
    with get_session() as db:
        for key,value in defaults.items():
            if not db.get(Setting,key): db.add(Setting(key=key,value=value))
        db.commit()

def list_records(kind):
    with get_session() as db: return [_record(r) for r in db.scalars(select(LegacyRecord).where(LegacyRecord.kind==kind).order_by(LegacyRecord.id.desc())).all()]

def add_record(kind,name,payload):
    with get_session() as db:
        row=LegacyRecord(kind=kind,name=name,payload=payload,created_at=now()); db.add(row); db.commit(); db.refresh(row); return _record(row)

def get_record(record_id):
    with get_session() as db:
        row=db.get(LegacyRecord,record_id); return _record(row) if row else None

def update_record(record_id,payload):
    with get_session() as db:
        row=db.get(LegacyRecord,record_id)
        if not row: return None
        row.payload={**row.payload,**payload}; row.name=str(payload.get("name",row.name)); db.commit(); db.refresh(row); return _record(row)

def delete_record(record_id):
    with get_session() as db:
        row=db.get(LegacyRecord,record_id)
        if not row: return False
        db.delete(row); db.commit(); return True

def get_setting(key,default=None):
    with get_session() as db:
        row=db.get(Setting,key); return row.value if row else default

def set_setting(key,value):
    with get_session() as db:
        row=db.get(Setting,key)
        if row: row.value=value
        else: db.add(Setting(key=key,value=value))
        db.commit(); return value
