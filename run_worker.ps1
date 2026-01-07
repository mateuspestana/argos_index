#!/usr/bin/env pwsh
# Script para executar o worker no Windows/PowerShell usando a .venv do uv

# Garante que estamos no diretório do script
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path)

$mode = if ($args.Count -gt 0) { $args[0] } else { "continuous" }

$python = Join-Path -Path ".venv" -ChildPath "Scripts/python.exe"
if (-not (Test-Path $python)) {
    $python = Join-Path -Path ".venv" -ChildPath "Scripts/python"
}

& $python main.py --mode $mode
