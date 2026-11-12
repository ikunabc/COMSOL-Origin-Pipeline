@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>&1
if errorlevel 1 (
  echo Please install uv and 64-bit Python 3.11 or 3.12, then run this file again.
  pause
  exit /b 1
)
git submodule update --init --recursive
if errorlevel 1 goto failed
uv sync --locked
if errorlevel 1 goto failed
echo Setup completed. Double-click Start-GUI.cmd to start.
pause
exit /b 0
:failed
echo Setup failed. Check the error above and retry.
pause
exit /b 1
