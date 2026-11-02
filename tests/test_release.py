"""Release safety boundaries without production database access."""
import json
import subprocess
import sys
from pathlib import Path
import pytest
from start import serve_options
from scripts.release_check import main


def test_local_defaults_and_single_worker():
    options=serve_options({})
    assert options['host']=='127.0.0.1' and options['threads']==1
    assert options['max_request_body_size']==100*1024*1024
    assert options['clear_untrusted_proxy_headers'] is True


@pytest.mark.parametrize('host',['0.0.0.0','::','example.com','127.0.0.2','localhost','127.0.0.1,0.0.0.0'])
def test_public_bind_rejected(host):
    with pytest.raises(ValueError,match='Public binding is blocked'):
        serve_options({'HOST':host})


@pytest.mark.parametrize('port',['0','65536','bad','-1'])
def test_invalid_port(port):
    with pytest.raises(ValueError,match='PORT'):
        serve_options({'PORT':port})


def test_public_gate_fails_and_writes_report(tmp_path):
    path=tmp_path/'gate.json'
    assert main(['--target','public','--output',str(path)])==2
    assert json.loads(path.read_text())['status']=='BLOCKED'
    assert main(['--target','local'])==0


def test_public_server_exits_before_database_import():
    import os
    env={**os.environ,'HOST':'0.0.0.0'}
    result=subprocess.run([sys.executable,'start.py'],cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True,timeout=10)
    assert result.returncode!=0 and 'Public binding is blocked' in result.stderr
    assert 'MongoDB' not in result.stderr


def test_package_excludes_private_files_and_is_reproducible(tmp_path):
    from scripts.package_release import package
    from zipfile import ZipFile
    root=tmp_path/'source';root.mkdir();(root/'server.py').write_text('print("safe")')
    (root/'.env').write_text('secret');(root/'data').mkdir();(root/'data'/'private.csv').write_text('private')
    (root/'app').mkdir();(root/'app'/'ok.py').write_text('ok')
    (root/'app'/'__pycache__').mkdir();(root/'app'/'__pycache__'/'bad.py').write_text('cache')
    a=package(root,tmp_path/'a.zip');b=package(root,tmp_path/'b.zip')
    assert a['sha256']==b['sha256']
    with ZipFile(tmp_path/'a.zip') as archive:
        assert set(archive.namelist())=={'server.py','app/ok.py','SOURCE_MANIFEST.json'}
        manifest=json.loads(archive.read('SOURCE_MANIFEST.json'))
        import hashlib
        for name,entry in manifest['files'].items():assert hashlib.sha256(archive.read(name)).hexdigest()==entry['sha256']


def test_waitress_local_http_smoke(monkeypatch):
    import importlib
    from threading import Thread, Event
    from urllib.request import urlopen
    import mongomock
    from persistence.mongo import _set_test_client
    from waitress import create_server
    _set_test_client(mongomock.MongoClient(),'release_smoke')
    app=importlib.import_module('server').app
    options=serve_options({});options['port']=0
    http=create_server(app,**options)
    stopped=Event()
    def serve_until_stopped():
        while not stopped.is_set():
            http.asyncore.loop(timeout=0.05,count=1,map=http._map)
    thread=Thread(target=serve_until_stopped,daemon=True);thread.start()
    try:
        base='http://127.0.0.1:'+str(http.effective_port)
        with urlopen(base+'/',timeout=10) as response:
            assert response.status==200 and b'AURA-BI' in response.read()
            assert response.headers['X-Content-Type-Options']=='nosniff'
        with urlopen(base+'/api/health',timeout=10) as response:
            assert json.load(response)['status']=='ready'
    finally:
        stopped.set();thread.join(timeout=5)
        http.close();http.task_dispatcher.shutdown()
    assert not thread.is_alive()
