"""CSV input compatibility without rewriting source bytes or categorical labels."""
import csv
from pathlib import Path
import pandas as pd


def read_csv_dataset(source, max_rows=None):
    path = isinstance(source, (str, Path))
    if path:
        with open(source,'rb') as stream: sample=stream.read(65536)
    else:
        source.seek(0);sample=source.read(65536);source.seek(0)
    if isinstance(sample,str):
        text=sample;encodings=[None]
    else:
        text=sample.decode('utf-8-sig',errors='replace')
        encodings=['utf-8-sig','cp1252','latin1']
    try:
        delimiter=csv.Sniffer().sniff(text,delimiters=',;\t|').delimiter
        detection='sniffed from bounded sample'
    except csv.Error:
        delimiter=',';detection='comma fallback; no reliable alternative detected'
    last=None
    for encoding in encodings:
        try:
            if not path: source.seek(0)
            frame=pd.read_csv(source,sep=delimiter,encoding=encoding,keep_default_na=False,na_values=[''], nrows=None if max_rows is None else max_rows + 1)
            frame.attrs['ingestion']={'delimiter':delimiter,'encoding':encoding or 'text stream','detection':detection,
                                      'missing_value_policy':'Only empty CSV fields are treated as missing; literal NA/NULL labels are retained.'}
            return frame
        except UnicodeDecodeError as error:
            last=error
    raise last
