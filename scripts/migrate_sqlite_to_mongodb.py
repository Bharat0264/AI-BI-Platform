"""Optional idempotent legacy SQLite workspace importer. Run --dry-run first."""
import argparse, json, sqlite3, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from persistence.mongo import initialize, get_database
def main():
    p=argparse.ArgumentParser(); p.add_argument("source",type=Path); p.add_argument("--dry-run",action="store_true"); args=p.parse_args()
    if not args.source.is_file(): raise SystemExit("Source SQLite database not found.")
    old=sqlite3.connect(args.source); old.row_factory=sqlite3.Row; initialize(); db=get_database(); counts={"legacy_records":0,"settings":0}
    for row in old.execute("SELECT id,kind,name,payload,created_at FROM records"):
        if db.legacy_records.find_one({"id":row["id"]}): continue
        counts["legacy_records"]+=1
        if not args.dry_run: db.legacy_records.insert_one({"id":row["id"],"kind":row["kind"],"name":row["name"],"payload":json.loads(row["payload"]),"created_at":row["created_at"]})
    for row in old.execute("SELECT key,value FROM settings"):
        if db.settings.find_one({"key":row["key"]}): continue
        counts["settings"]+=1
        if not args.dry_run: db.settings.insert_one({"key":row["key"],"value":json.loads(row["value"])})
    print(f"{'Would import' if args.dry_run else 'Imported'} {counts['legacy_records']} records and {counts['settings']} settings.")
if __name__ == "__main__": main()
