#!/bin/bash
# Script para rodar pytest com uv

cd "$(dirname "$0")"
uv run pytest tests/ -v --tb=short 2>&1 | tee pytest_results.txt
echo ""
echo "Resultados salvos em pytest_results.txt"
cat pytest_results.txt

