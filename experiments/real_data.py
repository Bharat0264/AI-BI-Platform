"""Public real-data checks with explicit metadata and independent arithmetic.

Run scripts/fetch_validation_data.py first. No provider or database calls occur.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import pandas as pd
from aura import AuraOrchestrator
from experiments.accuracy import Case, assess, summarize
from experiments.oracle import expected_output
from experiments.scope_checks import reference


def engine_csv(path):
    try:
        from app.ingestion import read_csv_dataset
    except ImportError:
        # The pre-fix reader's behavior, retained for a recorded baseline run.
        try: return pd.read_csv(path,encoding="utf-8")
        except UnicodeDecodeError: return pd.read_csv(path,encoding="latin1")
    return read_csv_dataset(path)


def evaluate(cache, local_retail=None, progress=False):
    manifest=json.loads((cache/'prepared-manifest.json').read_text(encoding='utf-8'))
    for source in manifest['sources']:
        if sha256((cache/source['archive_file']).read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('Source archive checksum mismatch')
    for name, entry in manifest['tables'].items():
        if sha256((cache/name).read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Prepared table checksum mismatch')
    datasets=[]
    for file in ('day.csv','hour.csv'):
        datasets.append({'id':file.removesuffix('.csv'),'source':'bike','file':cache/file,'delimiter':',','encoding':'utf-8',
                         'columns':['dteday','cnt','season','workingday'],'measure':'cnt','group':'season',
                         'corrections':{'dteday':'date/time','cnt':'quantity','season':'category','workingday':'category'}})
    datasets.append({'id':'bank','source':'bank','file':cache/'bank-full.csv','delimiter':';','encoding':'utf-8',
                     'columns':['campaign','job','month'],'measure':'campaign','group':'job',
                     'corrections':{'campaign':'quantity','job':'category','month':'generic categorical'}})
    if local_retail:
        from scripts.fetch_validation_data import retail_digest
        verified=retail_digest(local_retail,'cp1252')
        expected=next(source['canonical_rows_sha256'] for source in manifest['sources'] if source['id']=='retail')
        if verified['canonical_sha256']!=expected: raise ValueError('Local retail is not equivalent to the pinned source')
    datasets.append({'id':'retail','source':'retail','file':local_retail or cache/'retail-official.csv',
                     'delimiter':',','encoding':'cp1252' if local_retail else 'utf-8',
                     'columns':['Quantity','InvoiceDate','Country'],'measure':'Quantity','group':'Country',
                     'corrections':{'Quantity':'quantity','InvoiceDate':'date/time','Country':'region'},
                     'date_format':'%m/%d/%Y %H:%M' if local_retail else 'ISO'})
    engine=AuraOrchestrator(); results=[]; tables=[]
    for spec in datasets:
        if progress: print('Validating '+spec['id'],flush=True)
        with spec['file'].open(encoding=spec['encoding'],newline='') as stream:
            reader=csv.DictReader(stream,delimiter=spec['delimiter']); original_columns=reader.fieldnames
            records=[{key:row[key] for key in spec['columns']} for row in reader]
        source_hash=sha256(spec['file'].read_bytes()).hexdigest()
        source_frame=engine_csv(spec['file'])
        ingested_columns=len(source_frame.columns)
        valid_ingestion = set(spec['columns']).issubset(source_frame.columns) and len(source_frame) == len(records)
        if set(spec['columns']).issubset(source_frame.columns): source_frame=source_frame[spec['columns']].copy()
        original_frame=source_frame.copy(deep=True)
        tables.append({'table':spec['id'],'source':spec['source'],'file_sha256':source_hash,'rows':len(records),
                       'source_columns':len(original_columns),'validation_columns':spec['columns'],
                       'ingested_rows':len(source_frame),'ingested_columns_before_projection':ingested_columns,
                       'projection':'All rows; only declared task columns are passed to the engine; no records sampled or deleted.',
                       'corrections':spec['corrections'],'date_format':spec.get('date_format')})
        measure,group=spec['measure'],spec['group']
        cases=[Case(spec['id']+'-cold','unassisted',0,records,'What is quantity?','OK',expected_output(records,measure))]
        settings={'corrections':spec['corrections']}
        cases.extend([
            Case(spec['id']+'-total','metadata_configured',0,records,f'What is {measure}?','OK',expected_output(records,measure),settings),
            Case(spec['id']+'-mean','metadata_configured',0,records,f'What is average {measure}?','OK',expected_output(records,measure,'mean'),settings),
            Case(spec['id']+'-group','metadata_configured',0,records,f'Show {measure} by {group}','OK',expected_output(records,measure,'sum',group),settings),
            Case(spec['id']+'-rank','metadata_configured',0,records,f'Which {group} has the highest {measure}?','OK',expected_output(records,measure,'sum',group,'highest'),settings),
            Case(spec['id']+'-revenue-missing','safe_refusal',0,records,'What is revenue?','INSUFFICIENT DATA',{},settings)])
        label='1' if spec['source']=='bike' else 'admin.' if spec['id']=='bank' else 'France'
        filtered={'filters':{group:[label]}}
        cases.append(Case(spec['id']+'-filtered','metadata_configured',0,records,f'What is {measure}?','OK',reference(records,filtered,measure,'sum'),{**settings,'scope':filtered}))
        oracle_records=records
        if spec['source']=='bike':
            raw_scope={'date_column':'dteday','period':{'start':'2012-01-01','end':'2012-01-31'},'compare_to':{'start':'2011-01-01','end':'2011-01-31'}}
        elif spec['id']=='retail':
            if spec['date_format']!='ISO':
                oracle_records=[{**row,'InvoiceDate':datetime.strptime(row['InvoiceDate'],spec['date_format']).isoformat()} for row in records]
            raw_scope={'date_column':'InvoiceDate','period':{'start':'2011-01-01','end':'2011-01-31'},'compare_to':{'start':'2010-12-01','end':'2010-12-31'}}
            if spec['date_format']!='ISO':raw_scope['date_format']=spec['date_format']
        else:raw_scope=None
        if raw_scope:
            cases.append(Case(spec['id']+'-comparison','metadata_configured',0,records,f'What is {measure}?','OK',reference(oracle_records,raw_scope,measure,'sum'),{**settings,'scope':raw_scope}))
        else:
            invalid={'date_column':'month','period':{'start':'2010-01-01','end':'2010-01-31'}}
            cases.append(Case(spec['id']+'-no-invented-year','safe_refusal',0,records,f'What is {measure}?','INSUFFICIENT DATA',{}, {**settings,'scope':invalid}))
        for case in cases:
            started=time.perf_counter()
            try:
                if valid_ingestion:
                    response=engine.answer(case.question,source_frame,'real-'+spec['id'],**case.kwargs)
                    errors=assess(case,response)
                else:
                    response={'status':'INGESTION_ERROR','evidence':[]}
                    errors=['CSV ingestion lost required columns or records; calculations not attempted.']
                exception=None
            except Exception as error:
                response={'status':'EXCEPTION','evidence':[]};exception=type(error).__name__+': '+str(error);errors=[exception]
            results.append({'case_id':case.case_id,'table':spec['id'],'family':case.family,'seed':0,'question':case.question,
                            'expected_status':case.expected_status,'actual_status':response['status'],'passed':not errors,'errors':errors,
                            'expected':case.expected,'actual_evidence':response.get('evidence',[]),'exception':exception,
                            'latency_seconds':time.perf_counter()-started,'declared_settings':case.kwargs})
        pd.testing.assert_frame_equal(source_frame,original_frame)
        if sha256(spec['file'].read_bytes()).hexdigest()!=source_hash:raise ValueError('Source bytes changed')
    return {'sources':manifest['sources'],'tables':tables,'summary':summarize(results),'records':results,
            'local_retail_verification':manifest.get('local_retail')}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cache',type=Path,default=ROOT/'work'/'validation-public')
    parser.add_argument('--local-retail',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs'/'experiments'/'real_data')
    args=parser.parse_args()
    report=evaluate(args.cache,args.local_retail,progress=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    files=['aura/core.py','aura/scopes.py','aura/scoped_engine.py','experiments/real_data.py','experiments/oracle.py','experiments/scope_checks.py']
    if (ROOT/'app'/'ingestion.py').exists():files.append('app/ingestion.py')
    report['metadata']={'run_id':stamp,'python':sys.version,'source_hashes':{name:sha256((ROOT/name).read_bytes()).hexdigest() for name in files},
                        'scope':'Historical public data; developer-authored tasks. Four projected tables from three UCI releases, not four independent sources. No claims of real-user usability, general-domain accuracy or model superiority.'}
    args.output.mkdir(parents=True,exist_ok=True)
    target=args.output/f'real-{stamp}.json'
    target.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'report':str(target),'summary':report['summary'],'tables':report['tables']}))


if __name__=='__main__':main()
