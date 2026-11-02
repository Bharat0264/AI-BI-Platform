"""Request and import boundaries for the single-workspace application."""
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile, BadZipFile
from flask import request, jsonify
from werkzeug.exceptions import BadRequest, HTTPException


def validate_frame(frame):
    if len(frame) > 1_000_000 or len(frame.columns) > 200:
        raise BadRequest('Dataset exceeds the limit of 1,000,000 rows or 200 columns.')
    if frame.empty or not frame.columns.is_unique:
        raise BadRequest('Provide a nonempty dataset with unique column names.')
    if frame.memory_usage(index=True, deep=True).sum() > 512 * 1024 * 1024:
        raise BadRequest('Parsed dataset exceeds the 512 MB memory limit.')
    return frame


def validate_workbook(source):
    """Check ZIP metadata before Excel XML is decompressed; never extract files."""
    try:
        with ZipFile(source) as archive:
            members = archive.infolist()
            if len(members) > 2000 or sum(m.file_size for m in members) > 256 * 1024 * 1024:
                raise BadRequest('Excel workbook exceeds the expanded-size or member limit.')
            if any(m.flag_bits & 1 for m in members):
                raise BadRequest('Encrypted workbooks are not supported.')
    except BadZipFile as error:
        raise BadRequest('Invalid Excel workbook.') from error
    finally:
        if not isinstance(source, (str, Path)):
            source.seek(0)


def configure_security(app):
    app.config.update(MAX_FORM_MEMORY_SIZE=64 * 1024, MAX_FORM_PARTS=20)

    @app.before_request
    def browser_boundary():
        if not request.path.startswith('/api/'):
            return
        # GET report generation and analysis may also write artifacts.
        if request.headers.get('Sec-Fetch-Site') == 'cross-site':
            return jsonify(error='Cross-site API requests are not allowed.'), 403
        origin = request.headers.get('Origin')
        if origin:
            try:
                parsed = urlsplit(origin)
                expected = urlsplit(request.host_url)
                same = (parsed.scheme, parsed.netloc) == (expected.scheme, expected.netloc)
            except ValueError:
                same = False
            if not same:
                return jsonify(error='Use this application origin for API requests.'), 403
        if request.is_json and request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            if not isinstance(request.get_json(silent=True), dict):
                return jsonify(error='Provide a valid JSON object.'), 400

    @app.after_request
    def response_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(BadRequest)
    def invalid_request(error):
        return jsonify(error=error.description), 400

    @app.errorhandler(HTTPException)
    def api_http_error(error):
        if request.path.startswith('/api/'):
            return jsonify(error=error.description), error.code
        return error
