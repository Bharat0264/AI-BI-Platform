"""Import compatibility found using public banking/retail data, without network calls."""
from io import BytesIO
import importlib

import mongomock
import pandas as pd
import pytest

from persistence.mongo import _set_test_client


@pytest.fixture
def server_module():
    _set_test_client(mongomock.MongoClient(), 'ingestion_test')
    return importlib.import_module('server')


@pytest.mark.parametrize('delimiter', [',',';','\t','|'])
def test_delimiter_handling_preserves_quoted_values(server_module, delimiter):
    import csv,io
    stream=io.StringIO(newline='');writer=csv.writer(stream,delimiter=delimiter)
    writer.writerow(['campaign','job']);writer.writerow([2,'admin., senior']);writer.writerow([3,'services'])
    raw=stream.getvalue().encode('utf-8')
    source=BytesIO(raw)
    frame=server_module.read_dataset(source,'bank.csv')
    assert list(frame.columns)==['campaign','job']
    assert len(frame)==2 and frame.loc[0,'job']=='admin., senior'
    source.seek(0);assert source.read()==raw
    assert frame.attrs['ingestion']['delimiter']==delimiter


def test_bom_legacy_encoding_and_literal_category_codes(server_module):
    frame=server_module.read_dataset(BytesIO('\ufeffRevenue,Category\n10,NA\n20,NULL\n'.encode()),'data.csv')
    assert list(frame.columns)==['Revenue','Category']
    assert frame['Category'].tolist()==['NA','NULL']
    legacy=server_module.read_dataset(BytesIO('Revenue,Category\n10,Café\n'.encode('cp1252')),'legacy.csv')
    assert legacy.loc[0,'Category']=='Café'
    assert legacy.attrs['ingestion']['encoding']=='cp1252'


def test_general_data_does_not_become_sales_or_fake_zero_profit(server_module):
    df=pd.DataFrame({'instant':[1,2,3], 'dteday':['2011-01-01','2011-01-02','2011-01-03'], 'cnt':[50,100,70]})
    original=df.copy(deep=True)
    payload,status=server_module.analysis_payload(df,'day.csv')
    assert status==200 and payload['dashboard_mode']=='general'
    assert payload['metrics']==[] and payload['forecastTable']==[]
    assert payload['charts']['forecast']['values']==[]
    assert payload['rows']==3
    assert payload['datasetProfile']['columnMapping']=={}
    pd.testing.assert_frame_equal(df,original)


def test_missing_profit_never_becomes_a_measured_zero(server_module):
    df=pd.DataFrame({'Order Date':['2025-01-01'], 'Sales':[100.]})
    payload,status=server_module.analysis_payload(df,'sales.csv')
    assert status==200 and payload['dashboard_mode']=='general'
    assert payload['metrics']==[]


def test_explicit_financial_schema_and_total_amount_alias(server_module):
    from schema_engine import normalize_business_dataset
    df=pd.DataFrame({'Date':['2025-01-01'],'Total Amount':[100.],'Profit':[10.]})
    assert server_module.financial_dashboard_available(df)
    normalized,mapping,_=normalize_business_dataset(df)
    assert mapping['Sales']=='Total Amount'
    assert normalized['Sales'].iloc[0]==100


def test_semicolon_general_upload_reaches_the_analyst(server_module, monkeypatch):
    server=server_module
    monkeypatch.setattr(server,'persist_active_dataset',lambda *args: None)
    monkeypatch.setitem(server.ACTIVE_DATASET,'df',None)
    monkeypatch.setitem(server.ACTIVE_DATASET,'source',None)
    raw=b'campaign;job;month\n2;admin.;may\n3;services;jun\n'
    response=server.app.test_client().post('/api/upload',data={'dataset':(BytesIO(raw),'bank.csv')},content_type='multipart/form-data')
    assert response.status_code==200
    assert response.get_json()['dashboard_mode']=='general'
    assert len(server.ACTIVE_DATASET['df'])==2
    assert list(server.ACTIVE_DATASET['df'].columns)==['campaign','job','month']


@pytest.mark.parametrize('format,value', [('%m/%d/%Y %H:%M','12/1/2010 8:26'),('%d/%m/%Y %H:%M','01/12/2010 08:26'),('%m/%d/%Y','12/1/2010'),('%d/%m/%Y','01/12/2010')])
def test_declared_source_date_format_is_explicit_and_recorded(format,value):
    from aura import AuraOrchestrator
    df=pd.DataFrame({'Quantity':[10], 'InvoiceDate':[value]})
    scope={'date_column':'InvoiceDate','period':{'start':'2010-12-01','end':'2010-12-01'},'date_format':format}
    result=AuraOrchestrator().answer('What is quantity?',df,scope=scope)
    assert result['status']=='OK'
    assert result['evidence'][0]['filters']['date']['source_date_format']==format
    assert result['claims'][0]['computed_value']==10
    without={k:v for k,v in scope.items() if k!='date_format'}
    assert AuraOrchestrator().answer('What is quantity?',df,scope=without)['status']=='INSUFFICIENT DATA'


def test_unknown_date_format_is_never_executed_or_guessed():
    from aura import AuraOrchestrator
    df=pd.DataFrame({'Quantity':[10],'InvoiceDate':['12/1/2010 8:26']})
    scope={'date_column':'InvoiceDate','period':{'start':'2010-12-01','end':'2010-12-01'},'date_format':'auto'}
    assert AuraOrchestrator().answer('What is quantity?',df,scope=scope)['status']=='INSUFFICIENT DATA'

def test_general_dataset_financial_report_refuses_without_computation(server_module,monkeypatch):
    from unittest.mock import Mock
    df=pd.DataFrame({'campaign':[2,3], 'job':['admin.','services']})
    monkeypatch.setattr(server_module,'dataset_from_request',lambda:(df,'bank.csv'))
    model=Mock(side_effect=AssertionError('Must not invent a financial forecast'))
    monkeypatch.setattr(server_module,'predict_sales',model)
    response=server_module.app.test_client().get('/api/report')
    assert response.status_code==400
    model.assert_not_called()

def test_general_preview_is_valid_json_with_missing_or_nonfinite_numbers(server_module):
    import json
    df=pd.DataFrame({'Quantity':[1.,None,float('inf')],'Category':['NA','NULL','Office']})
    payload,status=server_module.analysis_payload(df,'general.csv')
    assert status==200
    json.dumps(payload,allow_nan=False)
    assert payload['preview'][1]['Quantity'] is None
    assert payload['preview'][2]['Quantity'] is None
    assert payload['quality']['cleanRows']=='Not transformed'

def test_undated_financial_columns_keep_general_import_and_report_guard(server_module,monkeypatch):
    df=pd.DataFrame({'Sales':[10,20],'Profit':[2,3]})
    assert not server_module.financial_dashboard_available(df)
    payload,status=server_module.analysis_payload(df,'undated.csv')
    assert status==200 and payload['dashboard_mode']=='general'
    monkeypatch.setattr(server_module,'dataset_from_request',lambda:(df,'undated.csv'))
    assert server_module.app.test_client().get('/api/report').status_code==400

def test_financial_only_routes_cannot_bypass_general_dataset_guard(server_module,monkeypatch):
    df=pd.DataFrame({'instant':[1,2], 'dteday':['2011-01-01','2011-01-02'], 'cnt':[50,70]})
    with pytest.raises(ValueError,match='Financial views require'):
        server_module.prepare_dataset(df)
    monkeypatch.setattr(server_module,'dataset_from_request',lambda:(df,'day.csv'))
    response=server_module.app.test_client().post('/api/platform/alerts/evaluate',json={})
    assert response.status_code==400
