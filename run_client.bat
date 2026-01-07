@echo off
REM Wrapper para executar o cliente via PowerShell com duplo clique
setlocal

set SCRIPT_DIR=%~dp0
set PS1=%SCRIPT_DIR%run_client.ps1

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PS1%"

endlocal
