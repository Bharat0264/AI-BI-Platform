"""Real Flask routes with isolated account databases and mocked MongoDB transport."""
from io import BytesIO
import importlib
from concurrent.futures import ThreadPoolExecutor
import mongomock
from mongomock.gridfs import enable_gridfs_integration
import pytest
from authentication import auth_database,provision_user,principal_scope,principal
from persistence.mongo import _set_test_client,get_database


@pytest.fixture
def accounts(monkeypatch):
    enable_gridfs_integration()
    _set_test_client(mongomock.MongoClient(),'account_test')
    server=importlib.import_module('server')
    monkeypatch.setitem(server.app.config,'AURA_AUTH_REQUIRED',True)
    monkeypatch.setitem(server.app.config,'SECRET_KEY','test-key-for-account-isolation-only-123456789')
    monkeypatch.setitem(server.app.config,'SESSION_COOKIE_SECURE',False)
    monkeypatch.setattr(server.GeminiEvidenceProvider,'explain',lambda *args:None)
    ids={name:provision_user(name,'test-password-12345') for name in ['alice','bob']}
    return server,ids


def login(server,name='alice'):
    client=server.app.test_client()
    info=client.get('/api/auth/session').json
    result=client.post('/api/auth/login',json={'username':name,'password':'test-password-12345'},headers={'X-CSRF-Token':info['csrf_token']})
    assert result.status_code==200
    return client,{'X-CSRF-Token':result.json['csrf_token']}


def upload(client,headers,amount):
    result=client.post('/api/upload',headers=headers,data={'dataset':(BytesIO(f'Quantity,Region\n{amount},North\n'.encode()),'same.csv')})
    assert result.status_code==200


def test_all_existing_api_routes_require_identity(accounts):
    server,_=accounts;client=server.app.test_client()
    for rule in server.app.url_map.iter_rules():
        if not rule.rule.startswith('/api/') or rule.rule.startswith('/api/auth/') or rule.rule=='/api/health':continue
        path=rule.rule.replace('<artifact_id>','unknown').replace('<query_id>','unknown').replace('<kind>','history').replace('<int:record_id>','1')
        method=next(method for method in rule.methods if method not in {'HEAD','OPTIONS'})
        assert client.open(path,method=method).status_code==401,(path,method)


def test_login_csrf_bad_credentials_and_logout_revocation(accounts):
    server,_=accounts;c=server.app.test_client()
    assert c.post('/api/auth/login',json={'username':'alice','password':'test-password-12345'}).status_code==403
    token=c.get('/api/auth/session').json['csrf_token']
    result=c.post('/api/auth/login',json={'username':'alice','password':'incorrect'},headers={'X-CSRF-Token':token})
    assert result.status_code==401 and 'incorrect' in result.json['error']
    c,headers=login(server)
    cookie=c.get_cookie('session').value
    assert c.post('/api/reset').status_code==403
    assert c.post('/api/auth/logout',headers=headers).status_code==200
    assert c.get('/api/analysis').status_code==401
    stolen=server.app.test_client();stolen.set_cookie('session',cookie)
    assert stolen.get('/api/analysis').status_code==401


def test_accounts_cannot_read_answers_records_or_reset_each_other(accounts):
    server,ids=accounts;a,ah=login(server);b,bh=login(server,'bob')
    upload(a,ah,7);upload(b,bh,99)
    qa=a.post('/api/ask',json={'question':'What is Quantity?'},headers=ah)
    qb=b.post('/api/ask',json={'question':'What is Quantity?'},headers=bh)
    assert qa.status_code==qb.status_code==200
    assert '7.00' in qa.json['answer'] and '99.00' in qb.json['answer']
    assert qa.json['query_id']!=qb.json['query_id']
    # Guessing identifiers or providing a victim workspace never switches database ownership.
    assert b.get('/api/aura/answers/'+qa.json['query_id']).status_code==404
    record=a.post('/api/platform/records/action',headers=ah,json={'name':'private task'}).json
    assert b.get('/api/platform/records/action').json==[]
    assert b.delete('/api/platform/records/action/'+str(record['id']),headers=bh).status_code==404
    spoof=b.post('/api/ask',headers=bh,json={'question':'What is Quantity?','expected_workspace_id':'victim','user_id':ids['alice']})
    assert spoof.status_code==409
    assert a.post('/api/reset',headers=ah).status_code==200
    assert '99.00' in b.post('/api/ask',json={'question':'What is Quantity?'},headers=bh).json['answer']
    assert principal.get() is None


def test_shared_file_connector_disabled_for_accounts(accounts):
    server,_=accounts;c,h=login(server)
    assert c.post('/api/platform/connect',headers=h,json={'database':'data/private.db','table':'orders'}).status_code==403


def test_tampered_pickle_is_rejected_before_deserialization(accounts,monkeypatch):
    server,ids=accounts;c,h=login(server);upload(c,h,7)
    with principal_scope(ids['alice']):
        db=get_database();saved=db.settings.find_one({'key':'active_dataset'})
        saved['value']['signature']='forged'
        db.settings.update_one({'key':'active_dataset'},{'$set':{'value':saved['value']}})
    monkeypatch.setattr(server.pd,'read_pickle',lambda *a:pytest.fail('invalid signature must never be deserialized'))
    assert c.get('/api/analysis').status_code==409


def test_disabled_account_and_password_reset_revoke_sessions(accounts):
    server,_=accounts;c,h=login(server)
    provision_user('alice','new-test-password-456')
    assert c.get('/api/analysis').status_code==401
    auth_database().users.update_one({'username':'bob'},{'$set':{'disabled':True}})
    client=server.app.test_client();token=client.get('/api/auth/session').json['csrf_token']
    assert client.post('/api/auth/login',headers={'X-CSRF-Token':token},json={'username':'bob','password':'test-password-12345'}).status_code==401


def test_login_attempts_are_bounded(accounts):
    server,_=accounts;c=server.app.test_client();token=c.get('/api/auth/session').json['csrf_token']
    codes=[c.post('/api/auth/login',headers={'X-CSRF-Token':token},json={'username':'alice','password':'wrong'}).status_code for _ in range(11)]
    assert codes[:10]==[401]*10 and codes[-1]==429


def test_concurrent_accounts_use_independent_request_contexts(accounts):
    server,_=accounts;a,ah=login(server);b,bh=login(server,'bob')
    upload(a,ah,7);upload(b,bh,99)
    def ask(pair):
        c,h,amount=pair
        for _ in range(3):
            result=c.post('/api/ask',headers=h,json={'question':'What is Quantity?'})
            assert result.status_code==200 and amount in result.json['answer']
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(ask,[(a,ah,'7.00'),(b,bh,'99.00')]))
    assert principal.get() is None


def test_browser_signin_upload_logout_and_account_switch(accounts):
    server,_=accounts
    from playwright.sync_api import sync_playwright,expect
    from werkzeug.serving import make_server
    from threading import Thread
    import os
    from pathlib import Path
    http=make_server('127.0.0.1',0,server.app,threaded=True)
    thread=Thread(target=http.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as runtime:
            browser=runtime.chromium.launch(headless=True,channel='msedge' if os.name=='nt' else 'chromium')
            page=browser.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('https://cdn.plot.ly/**',lambda route:route.fulfill(content_type='application/javascript',body='window.Plotly={newPlot:()=>Promise.resolve(),Plots:{resize:()=>{}}};'))
            page.goto(f'http://127.0.0.1:{http.server_port}/')
            expect(page.locator('#accountLogin')).to_be_visible()
            page.locator('#accountUsername').fill('alice');page.locator('#accountPassword').fill('wrong')
            page.locator('#accountLoginButton').click()
            expect(page.locator('#accountLoginStatus')).to_contain_text('incorrect')
            page.locator('#accountPassword').fill('test-password-12345');page.locator('#accountLoginButton').click()
            expect(page.locator('#accountName')).to_have_text('alice')
            page.locator('#datasetFile').set_input_files({'name':'mine.csv','mimeType':'text/csv','buffer':b'Quantity,Region\n7,North\n'})
            page.locator('#analyzeCsvButton').click()
            expect(page.locator('#uploadStatus')).to_contain_text('Imported mine.csv')
            page.locator('nav a[data-page="assistant"]').click()
            page.locator('#question').fill('What is Quantity?');page.locator('#askButton').click()
            expect(page.locator('#answer')).to_contain_text('7.00')
            if os.getenv('AURA_UI_CAPTURE_DIR'):
                page.locator('.assistant').screenshot(path=str(Path(os.environ['AURA_UI_CAPTURE_DIR'])/'account-workspace.png'))
            page.locator('#accountLogout').click()
            expect(page.locator('#accountLogin')).to_be_visible()
            page.locator('#accountUsername').fill('bob');page.locator('#accountPassword').fill('test-password-12345');page.locator('#accountLoginButton').click()
            expect(page.locator('#accountName')).to_have_text('bob')
            expect(page.locator('#sourceLabel')).to_contain_text('No file added yet')
            expect(page.locator('#answer')).not_to_contain_text('7.00')
            assert errors==[]
            browser.close()
    finally:
        http.shutdown();thread.join(timeout=5)


def test_account_request_limit_does_not_block_other_account(accounts):
    server,ids=accounts
    from datetime import datetime,timedelta,timezone
    from hashlib import sha256
    import time
    a,ah=login(server);b,bh=login(server,'bob')
    identifier=sha256((ids['alice']+':general:'+str(int(time.time()//60))).encode()).hexdigest()
    auth_database().request_limits.update_one({'_id':identifier},{'$set':{'count':120,'expires_at':datetime.now(timezone.utc)+timedelta(minutes=2)}},upsert=True)
    assert a.get('/api/analysis').status_code==429
    assert b.get('/api/analysis').status_code==200


def test_missing_account_blob_returns_actionable_error(accounts):
    server,ids=accounts;c,h=login(server);upload(c,h,7)
    with principal_scope(ids['alice']):
        from gridfs import GridFS
        db=get_database();saved=db.settings.find_one({'key':'active_dataset'})['value']
        GridFS(db,collection='active_datasets').delete(saved['file_id'])
    response=c.get('/api/analysis')
    assert response.status_code==409 and 'Re-import' in response.json['error']
