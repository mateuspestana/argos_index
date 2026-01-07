#!/bin/bash
# Script para executar o cliente Streamlit

cd "$(dirname "$0")"
# Adiciona o diretório atual ao PYTHONPATH para encontrar o módulo argos
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
# Executa o app Streamlit a partir do diretório do cliente para que os caminhos das páginas funcionem
cd argos/client
../../.venv/bin/streamlit run app.py

