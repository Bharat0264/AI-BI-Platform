"""Validate declared retail line amounts, not inferred profit or booked revenue."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime,timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import pandas as pd
from aura import AuraOrchestrator
from app.ingestion import read_csv_dataset
from experiments.accuracy import Case,assess,summarize
from experiments.oracle import expected_output
from experiments.scope_checks import reference
from scripts.fetch_validation_data import retail_digest


def evaluate(path):
    sources=json.loads((ROOT/'benchmark'/'real_sources.json').read_text(encoding='utf-8'))
    pinned=next(source for source in sources if source['id']=='retail')
    verified=retail_digest(path,'cp1252')
    if verified['canonical_sha256']!=pinned['canonical_rows_sha256']:
        raise ValueError('Retail source does not match the verified official snapshot')
    print('Official retail equivalence verified',flush=True)
    raw_hash=sha256(path.read_bytes()).hexdigest()
    records=[]
    with path.open(encoding='cp1252',newline='') as stream:
        for row in csv.DictReader(stream):
            records.append({'Line Amount':str(Decimal(row['Quantity'])*Decimal(row['UnitPrice'])),
                            'InvoiceDate':datetime.strptime(row['InvoiceDate'],'%m/%d/%Y %H:%M').isoformat(),
                            'Country':row['Country']})
    frame=read_csv_dataset(path)[['Quantity','UnitPrice','InvoiceDate','Country']].copy()
    frame['Line Amount']=pd.to_numeric(frame['Quantity'])*pd.to_numeric(frame['UnitPrice'])
    # UCI describes UnitPrice as sterling. This is an explicit declared unit, not conversion.
    frame['Currency']='GBP'
    corrections={'Quantity':'quantity','UnitPrice':'price','InvoiceDate':'date/time','Country':'region',
                 'Line Amount':'revenue','Currency':'generic categorical'}
    settings={'corrections':corrections}
    scope={'filters':{'Country':['United Kingdom']},'date_column':'InvoiceDate','date_format':'%m/%d/%Y %H:%M',
           'period':{'start':'2011-01-01','end':'2011-01-31'},'compare_to':{'start':'2010-12-01','end':'2010-12-31'}}
    cases=[Case('line-total','declared_line_amount',0,records,'What is line amount?','OK',expected_output(records,'Line Amount'),settings),
           Case('line-mean','declared_line_amount',0,records,'What is average line amount?','OK',expected_output(records,'Line Amount','mean'),settings),
           Case('line-country','declared_line_amount',0,records,'Show line amount by country','OK',expected_output(records,'Line Amount','sum','Country'),settings),
           Case('line-period-comparison','declared_line_amount',0,records,'What is line amount?','OK',reference(records,scope,'Line Amount','sum'),{**settings,'scope':scope})]
    engine=AuraOrchestrator();rows=[]
    for case in cases:
        started=time.perf_counter();response=engine.answer(case.question,frame,'retail-declared-line-amount',**case.kwargs)
        errors=assess(case,response)
        rows.append({'case_id':case.case_id,'family':case.family,'seed':0,'question':case.question,'expected_status':case.expected_status,
                     'actual_status':response['status'],'passed':not errors,'errors':errors,'exception':None,
                     'expected':case.expected,'actual_evidence':response['evidence'],'latency_seconds':time.perf_counter()-started})
    if sha256(path.read_bytes()).hexdigest()!=raw_hash:raise ValueError('Original source changed')
    return {'source':pinned,'source_file_sha256':raw_hash,'source_verification':verified,
            'derivation':{'engine':'pandas numeric Quantity * UnitPrice on a derived copy',
                          'reference':'independent Decimal multiplication from original CSV fields',
                          'unit':'GBP, explicitly declared from publisher sterling metadata',
                          'excluded_records':0,'meaning':'Signed source line amount, including cancellations/adjustments; not profit or booked revenue.',
                          'projection':'All rows; source task columns and two declared derived columns; not a full-width load test.'},
            'summary':summarize(rows),'records':rows}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs'/'experiments'/'real_data')
    args=parser.parse_args();result=evaluate(args.source)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    files=['experiments/retail_amount.py','app/ingestion.py','aura/core.py','aura/scopes.py','aura/scoped_engine.py','experiments/oracle.py']
    result['metadata']={'run_id':stamp,'python':sys.version,'source_hashes':{name:sha256((ROOT/name).read_bytes()).hexdigest() for name in files}}
    args.output.mkdir(parents=True,exist_ok=True);target=args.output/f'line-amount-{stamp}.json'
    target.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'report':str(target),'summary':result['summary']}))


if __name__=='__main__':main()
