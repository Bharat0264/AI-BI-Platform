"""Waitress startup: loopback locally, HTTPS service with a temporary public-demo mode on Render."""
import os
import re
from dotenv import load_dotenv


def on_render(environ=None):
    env = os.environ if environ is None else environ
    return env.get('RENDER', '').lower() == 'true'


def public_demo_enabled(environ=None):
    env = os.environ if environ is None else environ
    default = 'true' if on_render(env) else 'false'
    return env.get('AURA_PUBLIC_DEMO', default).lower() == 'true'


def render_trusted_hosts(environ=None):
    env = os.environ if environ is None else environ
    hosts = [env.get('RENDER_EXTERNAL_HOSTNAME', '')]
    hosts += [host.strip() for host in env.get('AURA_TRUSTED_HOSTS', '').split(',') if host.strip()]
    if not hosts[0] or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?', host) for host in hosts):
        raise ValueError('Render requires RENDER_EXTERNAL_HOSTNAME and valid optional AURA_TRUSTED_HOSTS hostnames.')
    return list(dict.fromkeys(hosts + ['localhost', '127.0.0.1']))


def serve_options(environ=None):
    env = os.environ if environ is None else environ
    render = on_render(env)
    # Render must remain reachable even if an old local HOST setting was copied.
    host = '0.0.0.0' if render else env.get('HOST', '127.0.0.1')
    if render:
        if not public_demo_enabled(env) and env.get('AURA_AUTH_REQUIRED', 'true').lower() != 'true':
            raise ValueError('Render requires AURA_AUTH_REQUIRED=true. Hosted anonymous access is not allowed.')
        secret = env.get('AURA_SECRET_KEY', '')
        if len(secret) < 32:
            raise ValueError('Render requires AURA_SECRET_KEY: set a private random secret of at least 32 characters in Render Environment.')
        if env.get('AURA_COOKIE_SECURE', 'true').lower() != 'true':
            raise ValueError('Render requires AURA_COOKIE_SECURE=true for HTTPS sessions.')
        render_trusted_hosts(env)
    elif host not in {'127.0.0.1', '::1'}:
        raise ValueError('Public binding is blocked outside the authenticated Render profile. Use HOST=127.0.0.1 for local evaluation.')
    try:
        port = int(env.get('PORT', '10000'))
        if not 1 <= port <= 65535:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('PORT must be an integer from 1 to 65535.') from None
    options = dict(host=host, port=port, threads=1, connection_limit=16,
                   channel_timeout=30, max_request_body_size=100 * 1024 * 1024,
                   clear_untrusted_proxy_headers=True)
    if render:
        # Render terminates HTTPS at its load balancer, then forwards HTTP.
        # Use the known external scheme without trusting arbitrary proxy headers.
        options['url_scheme'] = 'https'
    return options


def main():
    load_dotenv()
    try:
        options = serve_options()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    from waitress import serve
    from server import app
    print(f"Starting AURA-BI on {options['host']}:{options['port']}", flush=True)
    serve(app, **options)


if __name__ == '__main__':
    main()
