"""Inspect preserved UCI archives without transforming their original bytes."""
from __future__ import annotations
import csv, hashlib, io, json, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
RAW = ROOT / "raw"
SOURCES = {
 "online-shoppers.zip": {"source_id":"uci-online-shoppers","url":"https://archive.ics.uci.edu/static/public/468/online+shoppers+purchasing+intention+dataset.zip","member":"online_shoppers_intention.csv"},
 "bank-marketing.zip": {"source_id":"uci-bank-marketing","url":"https://archive.ics.uci.edu/static/public/222/bank+marketing.zip","member":"bank-additional/bank-additional-full.csv", "nested":"bank-additional.zip"},
 "online-retail.zip": {"source_id":"uci-online-retail","url":"https://archive.ics.uci.edu/static/public/352/online+retail.zip","member":"Online Retail.xlsx"},
}
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1<<20),b""): h.update(chunk)
    return h.hexdigest()
def inspect(path, spec):
    with zipfile.ZipFile(path) as z:
        container = zipfile.ZipFile(io.BytesIO(z.read(spec["nested"]))) if spec.get("nested") else z
        if spec["member"] not in container.namelist(): raise ValueError("expected member absent")
        member=container.read(spec["member"])
        if spec["member"].endswith(".csv"):
            rows=list(csv.reader(member.decode("utf-8-sig", errors="replace").splitlines(), delimiter=";" if spec["source_id"]=="uci-bank-marketing" else ","))
            header=rows[0]; data=rows[1:]
            missing={name:sum(not row[i].strip() if i<len(row) else True for row in data) for i,name in enumerate(header)}
            schema={name:"string" for name in header}
            return {"rows":len(data),"columns":len(header),"schema":schema,"missing_values":missing,"archive_members":z.namelist()}
        import pandas as pd
        frame = pd.read_excel(io.BytesIO(member))
        return {"rows":len(frame),"columns":len(frame.columns),"schema":{str(k):str(v) for k,v in frame.dtypes.items()},"missing_values":{str(k):int(v) for k,v in frame.isna().sum().items()},"archive_members":z.namelist()}
def main():
    records=[]
    for filename,spec in SOURCES.items():
        path=RAW/filename
        if not path.exists(): records.append({"source_id":spec["source_id"],"status":"NOT_RETRIEVED"}); continue
        try:
            records.append({"source_id":spec["source_id"],"status":"VERIFIED_ARCHIVE","retrieved_at":datetime.now(timezone.utc).isoformat(),"source_url":spec["url"],"filename":filename,"bytes":path.stat().st_size,"sha256":sha(path),**inspect(path,spec)})
        except Exception as exc: records.append({"source_id":spec["source_id"],"status":"INVALID_OR_INCOMPLETE_ARCHIVE","filename":filename,"bytes":path.stat().st_size,"sha256":sha(path),"error":str(exc)})
    (ROOT/"acquisition_manifest.json").write_text(json.dumps({"generated_at":datetime.now(timezone.utc).isoformat(),"records":records},indent=2),encoding="utf-8")
if __name__=="__main__": main()
