$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$previousCachePrefix = $env:PYTHONPYCACHEPREFIX
$env:PYTHONPYCACHEPREFIX = Join-Path $projectRoot '.runtime\pycache'

Push-Location -LiteralPath $projectRoot
try {
    $python = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3 -m venv .venv
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            & python -m venv .venv
        } else {
            throw 'Instala Python 3.11 o superior antes de continuar.'
        }
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear .venv.' }
    }
    & $python -m pip --version *> $null
    if ($LASTEXITCODE -ne 0) { & $python -m ensurepip --upgrade }
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias Python.' }
    if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) { throw 'Instala pnpm 11 y Node 22.12 o superior antes de continuar.' }
    pnpm --dir frontend install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias Vue.' }
    pnpm --dir frontend build
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar el frontend.' }
    Write-Host 'Entorno listo. Revisa .env.example, configura SQL Server e inicia con iniciar.cmd.'
} finally {
    Pop-Location
    $env:PYTHONPYCACHEPREFIX = $previousCachePrefix
}
