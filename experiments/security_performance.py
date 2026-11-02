"""Reproduce full-row scope timing with an in-memory pre-optimization baseline."""
import argparse, json, platform, statistics, time, tracemalloc
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pandas as pd
from aura import scopes
from aura.core import SemanticField

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',default='data/data.csv');parser.add_argument('--output',required=True);args=parser.parse_args()
    df=pd.read_csv(args.source,usecols=['InvoiceDate'],encoding='cp1252')
    fields=[SemanticField('InvoiceDate','date/time',1,'explicit metadata')]
    request={'date_column':'InvoiceDate','date_format':'%m/%d/%Y %H:%M','period':{'start':'2011-01-01','end':'2011-01-31'}}
    source=Path(scopes.__file__).read_text();baseline={}
    exec(compile(source.replace('for value in selected.drop_duplicates()', 'for value in selected'),'<baseline_scopes>','exec'),baseline)
    functions={'before':baseline['compile_scope'],'after':scopes.compile_scope}
    samples={label:[] for label in functions};audits=[]
    for iteration in range(3):
        for label in (['before','after'] if iteration % 2 == 0 else ['after','before']):
            start=time.perf_counter();result=functions[label](df,fields,request)
            samples[label].append(time.perf_counter()-start);audits.append(result['current']['audit'])
    results={label:{'seconds':times,'median_seconds':statistics.median(times)} for label,times in samples.items()}
    assert all(item==audits[0] for item in audits)
    tracemalloc.start();scopes.compile_scope(df,fields,request);_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    result={'python':platform.python_version(),'pandas':pd.__version__,'rows':len(df),'distinct_dates':df.InvoiceDate.nunique(),'repetitions':3,'results':results,'speedup':results['before']['median_seconds']/results['after']['median_seconds'],'identical_selection_audit':audits[0],'after_python_peak_bytes':peak,'limitations':'Scope compilation only, alternating sequential local runs; tracemalloc is Python allocation peak, not process RSS; no concurrent HTTP or production database benchmark.'}
    Path(args.output).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
