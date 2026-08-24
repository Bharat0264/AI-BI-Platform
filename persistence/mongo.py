"""Reusable MongoDB infrastructure for AURA-BI."""
from __future__ import annotations
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient
from pymongo.errors import PyMongoError

load_dotenv()
_client = None

def get_client():
    global _client
    if _client is None:
        uri=os.getenv("MONGODB_URI")
        if not uri: raise RuntimeError("MongoDB persistence requires MONGODB_URI.")
        try:
            _client=MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, appname="aura-bi")
        except Exception as exc:
            raise RuntimeError("MongoDB connection configuration is invalid or unavailable.") from exc
    return _client

def get_database():
    name=os.getenv("MONGODB_DATABASE")
    if not name: raise RuntimeError("MongoDB persistence requires MONGODB_DATABASE.")
    return get_client()[name]

def ping_database():
    try:
        get_client().admin.command("ping")
    except Exception as exc:
        raise RuntimeError("MongoDB is unavailable; verify configured connectivity.") from exc
    return True

def ensure_indexes():
    db=get_database()
    unique=[("workspaces","workspace_id"),("datasets","dataset_id"),("analytics_evidence","evidence_id"),("analytics_runs","analytics_run_id"),("ml_runs","ml_run_id"),("anomaly_investigations","investigation_id"),("ai_queries","query_id"),("reports","report_id")]
    for collection,key in unique: db[collection].create_index([(key,ASCENDING)],unique=True)
    for collection in ("datasets","analytics_evidence","analytics_runs","ml_runs","anomaly_investigations","ai_queries","reports","semantic_schemas","dataset_profiles"):
        # `datasets.dataset_id` is already the unique stable-ID index above.
        if collection != "datasets":
            db[collection].create_index([("dataset_id",ASCENDING)])
        db[collection].create_index([("workspace_id",ASCENDING)])
    db["semantic_schemas"].create_index([("dataset_id",ASCENDING),("column_name",ASCENDING)],unique=True)

def initialize():
    ping_database(); ensure_indexes()
    db=get_database(); db["schema_versions"].update_one({"version":1},{"$setOnInsert":{"version":1,"name":"initial_aura_mongo_schema","applied_at":datetime.now(timezone.utc).isoformat()}},upsert=True)
    return True

def _set_test_client(client, database="aura_test"):
    """Test-only hook; application code always uses configured MongoDB."""
    global _client
    _client=client
    os.environ["MONGODB_DATABASE"]=database
