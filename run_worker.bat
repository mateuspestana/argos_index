@echo off
REM Wrapper para executar o worker via PowerShell com duplo clique (modo default: continuous)
setlocal

set SCRIPT_DIR=%~dp0
set PS1=%SCRIPT_DIR%run_worker.ps1

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*

endlocal
