@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPYCACHEPREFIX=%~dp0.runtime\pycache"
if not exist ".venv\Scripts\python.exe" (
    echo Falta preparar Python. Ejecuta powershell -ExecutionPolicy Bypass -File scripts\preparar.ps1
    pause
    exit /b 1
)
if /i "%~1"=="--compilado" (
    ".venv\Scripts\python.exe" -m app.run
) else (
    ".venv\Scripts\python.exe" -m app.run --dev
)
set "RESULTADO=%errorlevel%"
pause
exit /b %RESULTADO%
