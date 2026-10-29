#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
if [ -d vendor/wheels ]; then
  .venv/bin/python -m pip install --no-index --find-links vendor/wheels --require-hashes -r requirements.lock
else
  .venv/bin/python -m pip install --require-hashes -r requirements.lock
fi
exec .venv/bin/python deriv_server.py "$@"
