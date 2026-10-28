@echo off
setlocal
if not exist "%~dp0.venv\Scripts\cli-anything-toutiao.exe" goto missing
"%~dp0.venv\Scripts\cli-anything-toutiao.exe" %*
exit /b %errorlevel%
:missing
echo Please run: powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"
exit /b 1
