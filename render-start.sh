#!/usr/bin/env sh
set -eu

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "No python executable found on PATH."
  exit 127
fi

echo "Using Python: $($PYTHON_BIN --version)"
echo "Using pip: $($PYTHON_BIN -m pip --version)"
echo "Starting AI BI Platform on port ${PORT:-5000}"

exec "$PYTHON_BIN" -m gunicorn app.dashboard:server --bind "0.0.0.0:${PORT:-5000}"
