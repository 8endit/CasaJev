#!/bin/zsh
set -eu
CASAJEV_PROJECT="$(cd "$(dirname "$0")" && pwd)"
CASAJEV_NPM="$(command -v npm || true)"
if [ -z "$CASAJEV_NPM" ]; then
  echo 'CasaJev-Entwicklung benötigt Node.js und npm.'
  exit 1
fi
cd "$CASAJEV_PROJECT/desktop"
if [ ! -x node_modules/.bin/electron ]; then
  "$CASAJEV_NPM" install
fi
exec "$CASAJEV_NPM" run dev
