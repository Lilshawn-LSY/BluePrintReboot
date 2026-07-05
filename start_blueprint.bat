@echo off
setlocal

set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\run_app.ps1"
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo BluePrintReboot launcher exited with code %EXITCODE%.
    echo If this is a fresh clone, open PowerShell here and run .\scripts\dev_setup.ps1.
    pause
)

exit /b %EXITCODE%
