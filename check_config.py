#!/usr/bin/env python3
"""
Script de diagnóstico de configuração do Argos Index
Verifica se o .env está correto e se as configurações estão sendo lidas
"""

import sys
import os
from pathlib import Path

# Adiciona diretório ao path
sys.path.insert(0, '.')

print("=" * 60)
print("Argos Index - Diagnóstico de Configuração")
print("=" * 60)
print()

# 1. Verifica arquivo .env
print("1. Verificando arquivo .env:")
env_file = Path('.env')
if env_file.exists():
    print(f"   ✅ Arquivo .env existe")
    print(f"   📁 Caminho: {env_file.absolute()}")
    print(f"   📊 Tamanho: {env_file.stat().st_size} bytes")
    
    # Verifica encoding
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            first_line = f.readline()
            print(f"   📝 Primeira linha: {repr(first_line[:50])}")
    except UnicodeDecodeError as e:
        print(f"   ❌ Erro de encoding: {e}")
        print(f"   💡 Tente salvar o arquivo como UTF-8")
except Exception as e:
    print(f"   ❌ Erro ao ler arquivo: {e}")
else:
    print(f"   ⚠️  Arquivo .env não encontrado")
    print(f"   💡 Copie .env.example para .env: cp .env.example .env")

print()

# 2. Tenta carregar .env
print("2. Carregando variáveis do .env:")
try:
    from dotenv import load_dotenv
    result = load_dotenv('.env', override=False)
    if result:
        print(f"   ✅ .env carregado com sucesso")
    else:
        print(f"   ⚠️  .env não foi carregado (pode não existir)")
except Exception as e:
    print(f"   ❌ Erro ao carregar .env: {type(e).__name__}: {e}")
    print(f"   💡 Verifique se o arquivo está no formato correto")
    print(f"   💡 Cada linha deve ser: VARIAVEL=valor")
    print(f"   💡 Linhas começando com # são comentários")
    import traceback
    traceback.print_exc()

print()

# 3. Verifica variáveis importantes
print("3. Variáveis de ambiente carregadas:")
vars_to_check = [
    "ARGOS_WATCH_DIR",
    "ARGOS_DB_TYPE",
    "ARGOS_SQLITE_DB_PATH",
    "ARGOS_LOG_LEVEL",
    "ARGOS_BATCH_SIZE",
]

for var in vars_to_check:
    value = os.getenv(var, "NÃO DEFINIDO")
    if value != "NÃO DEFINIDO":
        print(f"   ✅ {var} = {value}")
    else:
        print(f"   ⚠️  {var} = {value} (usando padrão)")

print()

# 4. Testa importação do config
print("4. Testando configuração do sistema:")
try:
    from argos.config import (
        WATCH_DIRECTORY, DB_TYPE, SQLITE_DB_PATH,
        LOG_LEVEL, BATCH_SIZE, PROJECT_ROOT
    )
    
    print(f"   ✅ Configurações carregadas com sucesso")
    print(f"   📁 PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"   📁 WATCH_DIRECTORY: {WATCH_DIRECTORY}")
    print(f"   📁 Tipo: {type(WATCH_DIRECTORY)}")
    
    if isinstance(WATCH_DIRECTORY, Path):
        exists = WATCH_DIRECTORY.exists()
        is_dir = WATCH_DIRECTORY.is_dir() if exists else False
        print(f"   📂 Existe: {exists}")
        if exists:
            print(f"   📂 É diretório: {is_dir}")
            if is_dir:
                # Conta arquivos .ufdr
                ufdr_files = list(WATCH_DIRECTORY.glob("*.ufdr"))
                print(f"   📄 Arquivos .ufdr encontrados: {len(ufdr_files)}")
        else:
            print(f"   ⚠️  Diretório não existe! Crie o diretório ou ajuste ARGOS_WATCH_DIR no .env")
    
    print(f"   💾 DB_TYPE: {DB_TYPE}")
    print(f"   💾 SQLITE_DB_PATH: {SQLITE_DB_PATH}")
    print(f"   📊 LOG_LEVEL: {LOG_LEVEL}")
    print(f"   📊 BATCH_SIZE: {BATCH_SIZE}")
    
except Exception as e:
    print(f"   ❌ Erro ao importar configurações: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print()

# 5. Testa watcher
print("5. Testando watcher:")
try:
    from argos.watcher.monitor import UFDRMonitor
    
    monitor = UFDRMonitor()
    print(f"   ✅ UFDRMonitor criado com sucesso")
    print(f"   📁 Diretório monitorado: {monitor.watch_directory}")
    print(f"   📂 Existe: {monitor.watch_directory.exists()}")
    
    if monitor.watch_directory.exists():
        # Faz scan
        new_files = monitor.scan()
        print(f"   📄 Arquivos novos encontrados: {len(new_files)}")
        if new_files:
            print(f"   📋 Primeiros arquivos:")
            for f in new_files[:3]:
                print(f"      - {f.name}")
    
except Exception as e:
    print(f"   ❌ Erro ao testar watcher: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("Diagnóstico concluído!")
print("=" * 60)

