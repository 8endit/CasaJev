$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $Uv) {
    Write-Error 'CasaJev benötigt uv: https://docs.astral.sh/uv/'
}
$Docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $Docker) {
    Write-Error 'CasaJev benötigt unter Windows Docker Desktop für den isolierten Werkzeug-Worker.'
}
& docker info *> $null
if ($LASTEXITCODE -ne 0) { Write-Error 'Docker Desktop ist nicht gestartet oder nicht zugänglich.' }
$WorkerImage = if ($env:CASAJEV_WORKER_IMAGE) { $env:CASAJEV_WORKER_IMAGE } else { 'python:3.11-slim' }
& docker image inspect $WorkerImage *> $null
if ($LASTEXITCODE -ne 0) { & docker pull $WorkerImage }
Set-Location $ProjectDir
$DataDir = if ($env:CASAJEV_HOME) { $env:CASAJEV_HOME } else { Join-Path $ProjectDir '.casajev' }
& uv sync --project $ProjectDir --extra local
& uv run --project $ProjectDir playwright install chromium
Start-Job -ScriptBlock { Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8787' } | Out-Null
& uv run --project $ProjectDir casajev --home $DataDir serve
