"""Security boundaries and date optimization regression tests; no external services."""
from io import BytesIO
import importlib
from zipfile import ZipFile
import mongomock
import pandas as pd
import pytest
from flask import Flask
from security import configure_security, validate_workbook, validate_frame
from persistence.mongo import _set_test_client

@pytest.fixture
def client():
    app=Flask(__name__);configure_security(app)
    @app.route('/api/change', methods=['GET','POST'])
    def change(): return {'ok':True}
    return app.test_client()

@pytest.mark.parametrize('method', ['get','post'])
def test_cross_site_rejected(client, method):
    for headers in [{'Origin':'https://evil.example'}, {'Origin':'null'}, {'Sec-Fetch-Site':'cross-site'}]:
        assert getattr(client,method)('/api/change',headers=headers).status_code==403
    assert getattr(client,method)('/api/change',headers={'Origin':'http://localhost'}).status_code==200

@pytest.mark.parametrize('body', ['[]','null','123','"x"','{broken'])
def test_json_shape(client,body):
    assert client.post('/api/change',data=body,content_type='application/json').status_code==400

def test_headers(client):
    r=client.get('/api/change')
    assert r.headers['Cache-Control']=='no-store'
    assert r.headers['X-Content-Type-Options']=='nosniff'
    assert r.headers['X-Frame-Options']=='DENY'

def test_excel_expansion_and_invalid_zip():
    from werkzeug.exceptions import BadRequest
    source=BytesIO()
    with ZipFile(source,'w') as archive:
        for i in range(2001):archive.writestr(str(i),'')
    source.seek(0)
    with pytest.raises(BadRequest):validate_workbook(source)
    assert source.tell()==0
    with pytest.raises(BadRequest):validate_workbook(BytesIO(b'not zip'))

def test_shape_limit():
    from werkzeug.exceptions import BadRequest
    for frame in [pd.DataFrame(),pd.DataFrame([[1]*201]),pd.DataFrame([[1,2]],columns=['x','x'])]:
        with pytest.raises(BadRequest):validate_frame(frame)

def test_csv_bounded_and_bad_upload(monkeypatch):
    from app.ingestion import read_csv_dataset
    assert len(read_csv_dataset(BytesIO(b'x\n1\n2\n3\n4\n'),max_rows=2))==3
    _set_test_client(mongomock.MongoClient(),'security_test')
    server=importlib.import_module('server')
    monkeypatch.setattr(server,'persist_active_dataset',lambda *a: pytest.fail('must not persist'))
    assert server.app.test_client().post('/api/upload',data={'dataset':(BytesIO(b''),'empty.csv')}).status_code==400
    assert server.app.test_client().post('/api/ask',json={'question':'x'*2001}).status_code==400

def test_sqlite_missing_file_is_not_created(tmp_path,monkeypatch):
    _set_test_client(mongomock.MongoClient(),'security_test')
    server=importlib.import_module('server');monkeypatch.setattr(server,'ROOT_DIR',tmp_path)
    missing=tmp_path/'missing.sqlite'
    result=server.app.test_client().post('/api/platform/connect',json={'database':str(missing),'table':'orders'})
    assert result.status_code==400 and not missing.exists()
    assert str(tmp_path) not in result.json['error']

def test_duplicate_date_validation_still_rejects_bad_value():
    from aura.scopes import compile_scope,ScopeError
    from aura.core import SemanticField
    data=pd.DataFrame({'Date':['01/01/2011']*1000+['02/30/2011']})
    with pytest.raises(ScopeError):compile_scope(data,[SemanticField('Date','date/time',1,'confirmed')],{'date_column':'Date','date_format':'%m/%d/%Y','period':{'start':'2011-01-01','end':'2011-01-31'}})
