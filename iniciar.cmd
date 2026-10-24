@echo off
setlocal
cd /d "%~dp0"
if not exist ".tools\uv\uv.exe" (
    echo Falta preparar uv. Ejecuta powershell -ExecutionPolicy Bypass -File scripts\preparar.ps1
    pause
    exit /b 1
)
if /i "%~1"=="--compilado" (
    call uv.cmd run --frozen python -m app.run
) else (
    call uv.cmd run --frozen python -m app.run --dev
)
set "RESULTADO=%errorlevel%"
pause
exit /b %RESULTADO%
