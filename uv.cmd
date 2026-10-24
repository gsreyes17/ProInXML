@echo off
setlocal
set "UV_CACHE_DIR=%~dp0.runtime\uv-cache"
set "UV_PYTHON_INSTALL_DIR=%~dp0.tools\python"
if not exist "%~dp0.tools\uv\uv.exe" goto missing
"%~dp0.tools\uv\uv.exe" %*
exit /b %errorlevel%
:missing
echo Falta uv local. Ejecuta scripts\preparar.ps1 o utiliza uv instalado en PATH.
exit /b 1
