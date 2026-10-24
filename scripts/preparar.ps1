param([switch]$Navegador)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $uvBinary = Join-Path $projectRoot '.tools\uv\uv.exe'
    if (-not (Test-Path -LiteralPath $uvBinary)) {
        $env:UV_UNMANAGED_INSTALL = Join-Path $projectRoot '.tools\uv'
        Invoke-RestMethod 'https://astral.sh/uv/0.13.5/install.ps1' | Invoke-Expression
    }
    $env:UV_CACHE_DIR = Join-Path $projectRoot '.runtime\uv-cache'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot '.tools\python'
    if ($Navegador) { & $uvBinary sync --frozen --group browser }
    else { & $uvBinary sync --frozen }
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo sincronizar Python.' }
    if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) { throw 'Instala pnpm 11 y Node 22.12 o superior antes de continuar.' }
    pnpm --dir frontend install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias Vue.' }
    pnpm --dir frontend build
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar el frontend.' }
    Write-Host 'Entorno listo. Revisa .env.example, configura SQL Server e inicia con iniciar.cmd.'
} finally { Pop-Location }
