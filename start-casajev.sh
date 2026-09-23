#!/bin/sh
set -eu
CASAJEV_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CASAJEV_UV_BIN=$(command -v uv || true)
if [ -z "$CASAJEV_UV_BIN" ]; then
  echo 'CasaJev benötigt uv: https://docs.astral.sh/uv/' >&2
  exit 1
fi
if [ "$(uname -s)" != 'Darwin' ]; then
  command -v docker >/dev/null 2>&1 || {
    echo 'CasaJev benötigt unter Linux Docker Engine für den isolierten Werkzeug-Worker.' >&2
    exit 1
  }
  docker info >/dev/null 2>&1 || {
    echo 'Docker ist installiert, aber nicht gestartet oder nicht zugänglich.' >&2
    exit 1
  }
  docker image inspect "${CASAJEV_WORKER_IMAGE:-python:3.11-slim}" >/dev/null 2>&1 ||
    docker pull "${CASAJEV_WORKER_IMAGE:-python:3.11-slim}"
fi
cd "$CASAJEV_PROJECT_DIR"
CASAJEV_DATA_DIR=${CASAJEV_HOME:-$CASAJEV_PROJECT_DIR/.casajev}
"$CASAJEV_UV_BIN" sync --project "$CASAJEV_PROJECT_DIR" --extra local
"$CASAJEV_UV_BIN" run --project "$CASAJEV_PROJECT_DIR" playwright install chromium
(sleep 2; if command -v xdg-open >/dev/null 2>&1; then xdg-open http://127.0.0.1:8787 >/dev/null 2>&1; elif command -v open >/dev/null 2>&1; then open http://127.0.0.1:8787; fi) &
exec "$CASAJEV_UV_BIN" run --project "$CASAJEV_PROJECT_DIR" casajev --home "$CASAJEV_DATA_DIR" serve
