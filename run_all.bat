@echo off
REM Inicia worker e cliente em paralelo (janelas separadas) e mantém em execução
setlocal

set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%"

set PSH=powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass

start "Argos Worker" %PSH% -File "%SCRIPT_DIR%run_worker.ps1"
start "Argos Client" %PSH% -File "%SCRIPT_DIR%run_client.ps1"

echo Worker e cliente iniciados (janelas: "Argos Worker" e "Argos Client").
pause

popd
endlocal
