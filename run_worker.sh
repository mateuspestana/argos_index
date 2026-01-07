#!/bin/bash
# Script para executar o worker

cd "$(dirname "$0")"

MODE=${1:-once}

.venv/bin/python main.py --mode "$MODE"

