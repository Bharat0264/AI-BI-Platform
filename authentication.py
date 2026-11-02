"""Administrator-provisioned accounts, revocable sessions and tenant context."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import os
import re
import secrets
import time
from uuid import uuid4
from flask import current_app, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

PUBLIC_DEMO_PRINCIPAL = 'public-demo-workspace'
principal = ContextVar('aura_principal', default=None)
DUMMY_HASH = generate_password_hash('non-account-placeholder-for-timing')


@contextmanager
def principal_scope(user_id):
    token=principal.set(user_id)
    try: yield
    finally: principal.reset(token)


def tenant_database_name(base, user_id):
    if not re.fullmatch(r'[A-Za-z0-9_]{1,24}',base):
        raise RuntimeError('Authenticated MONGODB_DATABASE must use 1–24 letters, digits or underscores.')
    return base+'_u_'+sha256(str(user_id).encode()).hexdigest()[:32]


def auth_database():
    from persistence.mongo import get_client
    base=os.environ.get('MONGODB_DATABASE','')
    tenant_database_name(base,'validate')
    return get_client()[base+'_auth']


def normalize_username(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.@-]{3,80}',value):
        raise ValueError('Username must contain 3–80 letters, digits, dots, @, underscores or hyphens.')
    return value.lower()


def provision_user(username,password):
    username=normalize_username(username)
    if not isinstance(password,str) or not 12 <= len(password) <= 1024:
        raise ValueError('Use a password of 12–1,024 characters.')
    db=auth_database();db.users.create_index('username',unique=True);db.users.create_index('user_id',unique=True)
    db.sessions.create_index('expires_at',expireAfterSeconds=0)
    db.login_attempts.create_index('expires_at',expireAfterSeconds=0)
    db.request_limits.create_index('expires_at',expireAfterSeconds=0)
    user=db.users.find_one({'username':username})
    user_id=user['user_id'] if user else str(uuid4())
    db.users.update_one({'username':username},{'$set':{'password_hash':generate_password_hash(password),'disabled':False},'$setOnInsert':{'user_id':user_id}},upsert=True)
    user_id = db.users.find_one({'username':username})['user_id']
    db.sessions.delete_many({'user_id':user_id})
    # Schema and default records are created only in this account's namespace.
    with principal_scope(user_id):
        from platform_store import init_store,set_setting
        init_store();set_setting('current_user',{'name':username,'role':'Analyst','workspace':'My Workspace'})
    return user_id


def current_user():
    sid=session.get('sid')
    if not isinstance(sid,str):return None
    db=auth_database()
    record=db.sessions.find_one({'session_id':sha256(sid.encode()).hexdigest(),'expires_at':{'$gt':datetime.now(timezone.utc)}})
    if not record:return None
    return db.users.find_one({'user_id':record['user_id'],'disabled':False})


def configure_authentication(app):
    from start import on_render, serve_options, render_trusted_hosts, public_demo_enabled
    hosted=on_render()
    if hosted:
        serve_options()  # Enforce hosting security even when imported by another WSGI entry point.
        app.config['TRUSTED_HOSTS']=render_trusted_hosts()
    demo=public_demo_enabled()
    required=not demo and os.getenv('AURA_AUTH_REQUIRED','true' if hosted else 'false').lower()=='true'
    secret=os.getenv('AURA_SECRET_KEY','')
    if (required or demo) and len(secret)<32:
        raise RuntimeError('AURA_AUTH_REQUIRED requires an AURA_SECRET_KEY of at least 32 characters.')
    app.config.update(AURA_AUTH_REQUIRED=required,AURA_PUBLIC_DEMO=demo,SECRET_KEY=secret or None,
        SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',
        SESSION_COOKIE_SECURE=os.getenv('AURA_COOKIE_SECURE','true').lower()=='true',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8))

    @app.before_request
    def authorize():
        if not request.path.startswith('/api/'):return
        if app.config['AURA_PUBLIC_DEMO']:
            g.principal=PUBLIC_DEMO_PRINCIPAL
            g.principal_token=principal.set(PUBLIC_DEMO_PRINCIPAL)
            return
        if not app.config['AURA_AUTH_REQUIRED']:return
        user=current_user()
        if request.path not in {'/api/auth/session','/api/auth/login','/api/health'} and not user:
            return jsonify(error='Sign in to access this workspace.'),401
        if user:
            g.principal=user['user_id'];g.auth_username=user['username']
            g.principal_token=principal.set(user['user_id'])
        if user and not request.path.startswith('/api/auth/'):
            heavy = request.path in {'/api/aura/ml','/api/aura/root-cause','/api/report','/api/stocks/analyze'}
            bucket = 'heavy' if heavy else 'general'
            limit = 10 if heavy else 120
            now = datetime.now(timezone.utc)
            identifier = sha256((user['user_id']+':'+bucket+':'+str(int(time.time()//60))).encode()).hexdigest()
            from pymongo import ReturnDocument
            counter = auth_database().request_limits.find_one_and_update({'_id':identifier}, {'$inc':{'count':1}, '$setOnInsert':{'expires_at':now+timedelta(minutes=2)}},upsert=True,return_document=ReturnDocument.AFTER)
            if counter['count'] > limit:
                return jsonify(error='Request limit reached. Wait a minute and retry.'),429
        if request.method not in {'GET','HEAD','OPTIONS'}:
            expected=session.get('csrf')
            supplied=request.headers.get('X-CSRF-Token','')
            if not isinstance(expected,str) or not hmac.compare_digest(expected,supplied):
                return jsonify(error='Refresh the page and try again; the request token is missing or expired.'),403

    @app.teardown_request
    def release_principal(_error):
        token=g.pop('principal_token',None)
        if token is not None:principal.reset(token)

    @app.get('/api/auth/session')
    def session_info():
        if app.config['AURA_PUBLIC_DEMO']:return jsonify(auth_required=False,authenticated=False,public_demo=True)
        if not app.config['AURA_AUTH_REQUIRED']:return jsonify(auth_required=False,authenticated=True)
        if not session.get('csrf'):session['csrf']=secrets.token_urlsafe(32)
        return jsonify(auth_required=True,authenticated=bool(getattr(g,'principal',None)),
                       username=getattr(g,'auth_username',None),csrf_token=session['csrf'])

    @app.post('/api/auth/login')
    def login():
        if not app.config['AURA_AUTH_REQUIRED']:return jsonify(error='Accounts are not enabled.'),400
        body=request.get_json(silent=True) or {}
        try:username=normalize_username(body.get('username'))
        except ValueError:username='invalid'
        password=body.get('password')
        if not isinstance(password,str) or len(password)>1024:password=''
        db=auth_database();now=datetime.now(timezone.utc)
        # Shared database counters bound attempts across processes, without trusting proxy headers.
        window=int(time.time()//900)
        for key,limit in [('ip:'+str(request.remote_addr),30),('user:'+username,10)]:
            identifier=sha256((str(window)+':'+key).encode()).hexdigest()
            from pymongo import ReturnDocument
            counter=db.login_attempts.find_one_and_update({'_id':identifier},{'$inc':{'count':1},'$setOnInsert':{'expires_at':now+timedelta(minutes=30)}},upsert=True,return_document=ReturnDocument.AFTER)
            if counter['count']>limit:return jsonify(error='Too many sign-in attempts. Try again in 15 minutes.'),429
        user=db.users.find_one({'username':username,'disabled':False})
        valid=check_password_hash(user['password_hash'] if user else DUMMY_HASH,password)
        if not user or not valid:return jsonify(error='Username or password is incorrect.'),401
        old=session.get('sid')
        if isinstance(old,str):db.sessions.delete_one({'session_id':sha256(old.encode()).hexdigest()})
        session.clear();session.permanent=True
        sid=secrets.token_urlsafe(32);session['sid']=sid;session['csrf']=secrets.token_urlsafe(32)
        db.sessions.insert_one({'session_id':sha256(sid.encode()).hexdigest(),'user_id':user['user_id'],'expires_at':now+timedelta(hours=8)})
        return jsonify(authenticated=True,username=user['username'],csrf_token=session['csrf'])

    @app.post('/api/auth/logout')
    def logout():
        sid=session.get('sid')
        if isinstance(sid,str):auth_database().sessions.delete_one({'session_id':sha256(sid.encode()).hexdigest()})
        session.clear();return jsonify(authenticated=False)
