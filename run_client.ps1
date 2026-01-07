#!/usr/bin/env pwsh
# Script para executar o cliente Streamlit no Windows/PowerShell usando a .venv do uv

# Garante que estamos no diretório do script
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path)

# Adiciona o diretório atual ao PYTHONPATH
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$($env:PYTHONPATH);$(Get-Location)"
} else {
    $env:PYTHONPATH = (Get-Location).Path
}

$streamlit = Join-Path -Path ".venv" -ChildPath "Scripts/streamlit.exe"
if (-not (Test-Path $streamlit)) {
    $streamlit = Join-Path -Path ".venv" -ChildPath "Scripts/streamlit"
}

& $streamlit run argos/client/app.py
