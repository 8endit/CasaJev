#!/bin/zsh
set -eu
CASAJEV_PROJECT="$(cd "$(dirname "$0")" && pwd)"
CASAJEV_UV="$(command -v uv || true)"
if [ -z "$CASAJEV_UV" ] && [ -x "$HOME/.local/bin/uv" ]; then
  CASAJEV_UV="$HOME/.local/bin/uv"
fi
if [ -z "$CASAJEV_UV" ]; then
  echo 'CasaJev benötigt uv. Installation: https://docs.astral.sh/uv/'
  exit 1
fi
cd "$CASAJEV_PROJECT"
CASAJEV_DATA="${CASAJEV_HOME:-$CASAJEV_PROJECT/.casajev}"
if [ -z "${CASAJEV_HOME:-}" ] && [ -f "$CASAJEV_PROJECT/.state-location" ]; then
  CASAJEV_DATA="$(cat "$CASAJEV_PROJECT/.state-location")"
fi
if "$CASAJEV_UV" run --project "$CASAJEV_PROJECT" python -c 'import json,urllib.request; d=json.load(urllib.request.urlopen("http://127.0.0.1:8787/api/state",timeout=1)); assert d.get("app")=="CasaJev"' >/dev/null 2>&1; then
  open 'http://127.0.0.1:8787'
  exit 0
fi
"$CASAJEV_UV" sync --project "$CASAJEV_PROJECT" --extra local
"$CASAJEV_UV" run --project "$CASAJEV_PROJECT" playwright install chromium
(sleep 2; open 'http://127.0.0.1:8787') &
exec "$CASAJEV_UV" run --project "$CASAJEV_PROJECT" casajev --home "$CASAJEV_DATA" serve
