"""Render listener, HTTPS forwarding, security configuration and cache recovery."""
from http.cookies import SimpleCookie
from io import BytesIO
import json
from threading import Event,Thread
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import importlib
import mongomock
import pytest
from flask import Flask,jsonify,g
from waitress import create_server
from authentication import configure_authentication,provision_user,principal_scope
from persistence.mongo import _set_test_client,get_database
from security import configure_security
from start import serve_options


def render_environment():
    return {'RENDER':'true','PORT':'12345','HOST':'127.0.0.1',
            'RENDER_EXTERNAL_HOSTNAME':'ai-bi-platform-gud0.onrender.com',
            'AURA_SECRET_KEY':'render-fixture-secret-only-1234567890123456',
            'AURA_AUTH_REQUIRED':'true','AURA_COOKIE_SECURE':'true'}


def test_render_overrides_stale_local_host_and_uses_port():
    options=serve_options(render_environment())
    assert options['host']=='0.0.0.0' and options['port']==12345
    assert options['url_scheme']=='https' and options['threads']==1


@pytest.mark.parametrize('key,value,message',[
    ('AURA_AUTH_REQUIRED','false','AURA_AUTH_REQUIRED'),
    ('AURA_SECRET_KEY','','AURA_SECRET_KEY'),
    ('AURA_COOKIE_SECURE','false','AURA_COOKIE_SECURE'),
    ('RENDER_EXTERNAL_HOSTNAME','','RENDER_EXTERNAL_HOSTNAME'),
    ('RENDER_EXTERNAL_HOSTNAME','*.example.com','hostnames'),
])
def test_render_configuration_fails_early(key,value,message):
    env=render_environment();env[key]=value
    with pytest.raises(ValueError,match=message):serve_options(env)


def test_render_defaults_to_accounts_when_flag_absent(monkeypatch):
    for key,value in render_environment().items():monkeypatch.setenv(key,value)
    monkeypatch.delenv('AURA_AUTH_REQUIRED',raising=False)
    app=Flask(__name__);configure_authentication(app)
    assert app.config['AURA_AUTH_REQUIRED'] is True
    assert app.config['SESSION_COOKIE_SECURE'] is True
    assert 'ai-bi-platform-gud0.onrender.com' in app.config['TRUSTED_HOSTS']


def test_authenticated_startup_does_not_restore_legacy_cache(monkeypatch):
    _set_test_client(mongomock.MongoClient(),'render_restore')
    server=importlib.import_module('server')
    monkeypatch.setitem(server.app.config,'AURA_AUTH_REQUIRED',True)
    monkeypatch.setattr(server,'get_setting',lambda *args:pytest.fail('must not read a legacy active pointer'))
    monkeypatch.setattr(server.pd,'read_pickle',lambda *args:pytest.fail('must not read a legacy pickle'))
    server.restore_active_dataset()


def test_incompatible_account_pickle_returns_reimport_message(monkeypatch):
    from mongomock.gridfs import enable_gridfs_integration
    from gridfs import GridFS
    enable_gridfs_integration();_set_test_client(mongomock.MongoClient(),'render_pickle')
    server=importlib.import_module('server')
    monkeypatch.setitem(server.app.config,'AURA_AUTH_REQUIRED',True)
    monkeypatch.setitem(server.app.config,'SECRET_KEY','render-fixture-secret-only-1234567890123456')
    monkeypatch.setitem(server.app.config,'SESSION_COOKIE_SECURE',False)
    uid=provision_user('render-user','render-test-password')
    client=server.app.test_client();token=client.get('/api/auth/session').json['csrf_token']
    login=client.post('/api/auth/login',json={'username':'render-user','password':'render-test-password'},headers={'X-CSRF-Token':token})
    token=login.json['csrf_token']
    assert client.post('/api/upload',headers={'X-CSRF-Token':token},data={'dataset':(BytesIO(b'Quantity,Region\n7,North\n'),'old.csv')}).status_code==200
    with principal_scope(uid):
        saved=get_database().settings.find_one({'key':'active_dataset'})['value']
        assert saved['pandas_version']==server.pd.__version__
        blob_id=saved['file_id']
    def unsupported(*args):raise NotImplementedError('old pandas StringDtype')
    monkeypatch.setattr(server.pd,'read_pickle',unsupported)
    response=client.get('/api/analysis')
    assert response.status_code==409 and 'Re-import' in response.json['error']
    with principal_scope(uid):assert GridFS(get_database(),collection='active_datasets').exists(blob_id)


def test_render_listener_accepts_forwarded_https_origin_and_requires_login(monkeypatch):
    env=render_environment()
    for key,value in env.items():monkeypatch.setenv(key,value)
    _set_test_client(mongomock.MongoClient(),'render_http')
    uid=provision_user('render-user','render-test-password')
    app=Flask(__name__);configure_security(app);configure_authentication(app)
    @app.get('/api/probe')
    def probe():return jsonify(owner=g.principal)
    options=serve_options(env);options['port']=0
    http=create_server(app,**options)
    assert http.socket.getsockname()[0]=='0.0.0.0'
    stop=Event()
    def run():
        while not stop.is_set():http.asyncore.loop(timeout=.05,count=1,map=http._map)
    thread=Thread(target=run,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(http.effective_port)
    host=env['RENDER_EXTERNAL_HOSTNAME']
    try:
        with pytest.raises(HTTPError) as blocked:urlopen(Request(base+'/api/probe',headers={'Host':host}),timeout=10)
        assert blocked.value.code==401
        with urlopen(Request(base+'/api/auth/session',headers={'Host':host}),timeout=10) as response:
            info=json.load(response);cookies=SimpleCookie();cookies.load(response.headers['Set-Cookie'])
            assert cookies['session']['secure'] and cookies['session']['httponly']
            cookie='session='+cookies['session'].value
        request=Request(base+'/api/auth/login',data=json.dumps({'username':'render-user','password':'render-test-password'}).encode(),headers={'Host':host,'Origin':'https://'+host,'Cookie':cookie,'X-CSRF-Token':info['csrf_token'],'Content-Type':'application/json'})
        with urlopen(request,timeout=10) as response:
            assert json.load(response)['authenticated'] is True
            cookies=SimpleCookie();cookies.load(response.headers['Set-Cookie']);cookie='session='+cookies['session'].value
        with urlopen(Request(base+'/api/probe',headers={'Host':host,'Cookie':cookie}),timeout=10) as response:
            assert json.load(response)['owner']==uid
        with pytest.raises(HTTPError) as blocked:urlopen(Request(base+'/api/auth/session',headers={'Host':'untrusted.example'}),timeout=10)
        assert blocked.value.code==400
    finally:
        stop.set();thread.join(timeout=5);http.close();http.task_dispatcher.shutdown()
    assert not thread.is_alive()
