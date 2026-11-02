"""Local-only release candidate server; no public deployment bypass."""
import os
from dotenv import load_dotenv


def serve_options(environ=None):
    env = os.environ if environ is None else environ
    host = env.get('HOST', '127.0.0.1')
    if host not in {'127.0.0.1', '::1'}:
        raise ValueError('Public binding is blocked for this release candidate. Authentication, isolation and dependency review remain open. Use HOST=127.0.0.1 for local evaluation.')
    try:
        port = int(env.get('PORT', '10000'))
        if not 1 <= port <= 65535:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('PORT must be an integer from 1 to 65535.') from None
    return dict(host=host, port=port, threads=1, connection_limit=16,
                channel_timeout=30, max_request_body_size=100 * 1024 * 1024,
                clear_untrusted_proxy_headers=True)


def main():
    load_dotenv()
    try:
        options = serve_options()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    # Validate binding before importing the app, which initializes MongoDB.
    from waitress import serve
    from server import app
    serve(app, **options)


if __name__ == '__main__':
    main()
