import os

from waitress import serve

from server import app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    serve(app, host="0.0.0.0", port=port)
