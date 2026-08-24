"""Compatibility adapter: existing workspace endpoints now persist to MongoDB."""
from __future__ import annotations
from datetime import datetime, timezone
from pymongo import DESCENDING
from persistence.mongo import initialize, get_database

def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def init_store(): initialize(); db=get_database(); db.settings.update_one({"key":"current_user"},{"$setOnInsert":{"key":"current_user","value":{"name":"Bharath","role":"Admin","workspace":"Executive Workspace"}}},upsert=True); db.settings.update_one({"key":"semantic_metrics"},{"$setOnInsert":{"key":"semantic_metrics","value":[]}},upsert=True)
def _record(row): return {"id":row["id"],"kind":row["kind"],"name":row["name"],"payload":row["payload"],"created_at":row["created_at"]}
def list_records(kind): return [_record(r) for r in get_database().legacy_records.find({"kind":kind}).sort("id",DESCENDING)]
def add_record(kind,name,payload):
    db=get_database(); next_id=db.counters.find_one_and_update({"key":"legacy_records"},{"$inc":{"value":1}},upsert=True,return_document=True)["value"]; row={"id":next_id,"kind":kind,"name":name,"payload":payload,"created_at":now()}; db.legacy_records.insert_one(row); return _record(row)
def get_record(record_id):
    row=get_database().legacy_records.find_one({"id":record_id}); return _record(row) if row else None
def update_record(record_id,payload):
    db=get_database(); row=db.legacy_records.find_one_and_update({"id":record_id},{"$set":{"payload":{**(get_record(record_id) or {"payload":{}})["payload"],**payload},"name":str(payload.get("name",(get_record(record_id) or {"name":""})["name"]))}},return_document=True); return _record(row) if row else None
def delete_record(record_id): return get_database().legacy_records.delete_one({"id":record_id}).deleted_count > 0
def get_setting(key,default=None):
    row=get_database().settings.find_one({"key":key}); return row["value"] if row else default
def set_setting(key,value): get_database().settings.update_one({"key":key},{"$set":{"value":value}},upsert=True); return value
