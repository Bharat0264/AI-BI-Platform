"""Optional, idempotent import of legacy records/settings. Use --dry-run first."""
import argparse, json, sqlite3
from pathlib import Path
from persistence.database import get_session, init_database
from persistence.models import LegacyRecord, Setting
def main():
    p=argparse.ArgumentParser(); p.add_argument("source",type=Path); p.add_argument("--dry-run",action="store_true"); args=p.parse_args()
    if not args.source.is_file(): raise SystemExit("Source SQLite database not found.")
    old=sqlite3.connect(args.source); old.row_factory=sqlite3.Row; init_database(); imported=0
    with get_session() as db:
        for row in old.execute("SELECT id,kind,name,payload,created_at FROM records"):
            if db.get(LegacyRecord,row["id"]): continue
            imported+=1
            if not args.dry_run: db.add(LegacyRecord(id=row["id"],kind=row["kind"],name=row["name"],payload=json.loads(row["payload"]),created_at=row["created_at"]))
        for row in old.execute("SELECT key,value FROM settings"):
            if not db.get(Setting,row["key"]) and not args.dry_run: db.add(Setting(key=row["key"],value=json.loads(row["value"])))
        if not args.dry_run: db.commit()
    print(f"{'Would import' if args.dry_run else 'Imported'} {imported} legacy records; existing IDs were skipped.")
if __name__ == "__main__": main()
