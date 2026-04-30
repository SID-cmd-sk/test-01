@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start.ps1" %*
if errorlevel 1 (
  echo.
  echo Startup failed. Try opening PowerShell and running:
  echo   scripts\start.ps1 -Verbose
  echo.
  echo If execution policy blocks scripts, run:
  echo   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
  exit /b 1
)
endlocal
