"""Fetch pinned official public datasets; preserve source bytes and declare derivatives."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import io
import json
from pathlib import Path
import ssl
from urllib.request import urlopen
import zipfile
import certifi
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]


def canonical_retail_row(header, row):
    output = []
    for key, value in zip(header, row):
        if value is None or value == "":
            value = ""
        elif key == "InvoiceDate":
            if not isinstance(value, datetime):
                try:
                    value = datetime.fromisoformat(value)
                except ValueError:
                    value = datetime.strptime(value, "%m/%d/%Y %H:%M")
            value = value.isoformat(timespec="seconds")
        elif key in {"Quantity", "UnitPrice", "CustomerID"}:
            value = format(Decimal(str(value)).normalize(), "f")
        else:
            value = str(value)
        output.append(value)
    return output


def retail_digest(path, encoding):
    digest = sha256(); missing = {}; count = 0
    with path.open(encoding=encoding, newline="") as stream:
        reader = csv.reader(stream); header = next(reader)
        for row in reader:
            values = canonical_retail_row(header, row)
            for key, value in zip(header, values):
                if value == "": missing[key] = missing.get(key, 0) + 1
            digest.update((json.dumps(values,ensure_ascii=False,separators=(",", ":")) + "\n").encode())
            count += 1
    return {"rows": count, "canonical_sha256": digest.hexdigest(), "empty_cells": missing}


def prepare(cache, download=False, local_retail=None):
    cache.mkdir(parents=True,exist_ok=True)
    sources = json.loads((ROOT / "benchmark" / "real_sources.json").read_text(encoding="utf-8"))
    for source in sources:
        path = cache / source["archive_file"]
        if not path.exists():
            if not download: raise FileNotFoundError("Missing pinned data; run with --download: " + str(path))
            partial = path.with_suffix(".partial")
            with urlopen(source["url"],context=ssl.create_default_context(cafile=certifi.where()),timeout=60) as response, partial.open("wb") as target:
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk: break
                    total += len(chunk)
                    if total > 50 * 1024 * 1024: raise ValueError("Dataset exceeds the archive size limit")
                    target.write(chunk)
            if sha256(partial.read_bytes()).hexdigest() != source["sha256"]: raise ValueError("Downloaded archive checksum mismatch")
            partial.replace(path)
        if sha256(path.read_bytes()).hexdigest() != source["sha256"]: raise ValueError("Cached archive checksum mismatch: " + source["id"])
    # Only explicitly named members are read; never extract arbitrary archive paths.
    with zipfile.ZipFile(cache / "bike.zip") as archive:
        for name in ("day.csv", "hour.csv", "Readme.txt"):
            (cache / name).write_bytes(archive.read(name))
    with zipfile.ZipFile(cache / "bank.zip") as archive:
        with zipfile.ZipFile(io.BytesIO(archive.read("bank.zip"))) as inner:
            for name in ("bank-full.csv", "bank-names.txt"):
                (cache / name).write_bytes(inner.read(name))
    with zipfile.ZipFile(cache / "retail.zip") as archive:
        (cache / "Online Retail.xlsx").write_bytes(archive.read("Online Retail.xlsx"))
    derived = cache / "retail-official.csv"
    if not derived.exists():
        workbook = load_workbook(cache / "Online Retail.xlsx",read_only=True,data_only=True)
        with derived.open("w",encoding="utf-8",newline="") as target:
            writer = csv.writer(target)
            for row in workbook.active.iter_rows(values_only=True):
                writer.writerow([value.isoformat(sep=" ") if isinstance(value,datetime) else value for value in row])
        workbook.close()
    official = retail_digest(derived, "utf-8")
    expected = next(source["canonical_rows_sha256"] for source in sources if source["id"] == "retail")
    if official["canonical_sha256"] != expected: raise ValueError("Derived retail data does not match the pinned canonical values")
    manifest = {"sources": sources, "retail_official": official, "tables": {}}
    for name in ("day.csv", "hour.csv", "bank-full.csv", "retail-official.csv"):
        path = cache / name
        manifest["tables"][name] = {"bytes":path.stat().st_size,"sha256":sha256(path.read_bytes()).hexdigest()}
    if local_retail:
        local = retail_digest(local_retail, "cp1252")
        manifest["local_retail"] = {**local,"path":str(local_retail),
            "equivalent_under_declared_normalization":local["canonical_sha256"] == expected,
            "normalization":"All 8 source columns in row order; ISO seconds; Decimal text for Quantity/UnitPrice/CustomerID; empty cells to empty strings; exact remaining strings. Local dates explicitly MM/DD/YYYY HH:MM, decoded cp1252."}
    (cache / "prepared-manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cache",type=Path,default=ROOT/"work"/"validation-public")
    parser.add_argument("--download",action="store_true")
    parser.add_argument("--verify-local-retail",type=Path)
    args=parser.parse_args()
    manifest=prepare(args.cache,args.download,args.verify_local_retail)
    print(json.dumps({"cache":str(args.cache),"retail":manifest["retail_official"],"local":manifest.get("local_retail")}))


if __name__ == "__main__":main()
