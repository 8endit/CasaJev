$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopDir = Join-Path $ProjectDir 'desktop'
if (-not $env:CASAJEV_HOME) { $env:CASAJEV_HOME = Join-Path $env:LOCALAPPDATA 'CasaJev\state' }

foreach ($command in @('uv', 'node', 'npm', 'docker')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "CasaJev benötigt $command."
    }
}

& docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop ist nicht gestartet oder nicht zugänglich.' }

$WorkerImage = if ($env:CASAJEV_WORKER_IMAGE) { $env:CASAJEV_WORKER_IMAGE } else { 'python:3.11-slim' }
& docker image inspect $WorkerImage *> $null
if ($LASTEXITCODE -ne 0) { & docker pull $WorkerImage; if ($LASTEXITCODE -ne 0) { throw 'Das Docker-Worker-Image konnte nicht geladen werden.' } }

& uv sync --project $ProjectDir --python 3.11 --extra local
if ($LASTEXITCODE -ne 0) { throw 'Die Python-Abhängigkeiten konnten nicht eingerichtet werden.' }

if (-not (Test-Path -LiteralPath (Join-Path $DesktopDir 'node_modules'))) {
    & npm --prefix $DesktopDir install
    if ($LASTEXITCODE -ne 0) { throw 'Die Desktop-Abhängigkeiten konnten nicht eingerichtet werden.' }
}

Push-Location $DesktopDir
try {
    & npm start
} finally {
    Pop-Location
}
