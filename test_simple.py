#!/usr/bin/env python
"""
Teste simples para verificar se os módulos funcionam
"""

import sys
from pathlib import Path

def test_imports():
    """Testa imports básicos"""
    print("Testando imports...")
    try:
        from argos.config import get_database_url
        print("✓ Config importado")
        
        from argos.utils.hashing import calculate_string_hash
        print("✓ Hashing importado")
        
        from argos.utils.text_utils import normalize_text
        print("✓ Text utils importado")
        
        from argos.index.validators import validate_cpf
        print("✓ Validators importado")
        
        from argos.index.database import DatabaseManager
        print("✓ Database importado")
        
        from argos.index.extractor import UFDRExtractor
        print("✓ Extractor importado")
        
        from argos.index.text_extractor import TextExtractor
        print("✓ Text extractor importado")
        
        from argos.index.regex_engine import RegexEngine
        print("✓ Regex engine importado")
        
        from argos.watcher.detector import UFDRDetector
        print("✓ Watcher detector importado")
        
        from argos.watcher.monitor import UFDRMonitor
        print("✓ Watcher monitor importado")
        
        return True
    except Exception as e:
        print(f"✗ Erro ao importar: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_functions():
    """Testa funções básicas"""
    print("\nTestando funções básicas...")
    try:
        from argos.utils.hashing import calculate_string_hash
        hash1 = calculate_string_hash("teste")
        hash2 = calculate_string_hash("teste")
        assert hash1 == hash2, "Hash deve ser determinístico"
        assert len(hash1) == 64, "Hash deve ter 64 caracteres"
        print("✓ Hash funcionando")
        
        from argos.index.validators import validate_cpf
        # CPF válido de exemplo
        valid_cpf = "11144477735"
        result = validate_cpf(valid_cpf)
        assert isinstance(result, bool), "Validação deve retornar bool"
        print("✓ Validator funcionando")
        
        from argos.config import get_database_url
        url = get_database_url()
        assert url.startswith("sqlite:///"), "URL deve ser SQLite"
        print("✓ Config funcionando")
        
        return True
    except Exception as e:
        print(f"✗ Erro nas funções: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database():
    """Testa banco de dados"""
    print("\nTestando banco de dados...")
    try:
        import tempfile
        from argos.index.database import DatabaseManager
        
        # Cria banco temporário
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        db_path = f"sqlite:///{temp_db.name}"
        
        db_manager = DatabaseManager(database_url=db_path)
        db_manager.create_tables()
        print("✓ Tabelas criadas")
        
        # Testa inserção
        ufdr_id = "a" * 64
        db_manager.add_ufdr_file(ufdr_id, "test.ufdr")
        print("✓ UFDR file adicionado")
        
        # Verifica se foi salvo
        is_processed = db_manager.is_ufdr_processed(ufdr_id)
        assert is_processed, "UFDR deve estar processado"
        print("✓ Verificação de processamento funcionando")
        
        # Limpa
        import os
        os.unlink(temp_db.name)
        
        return True
    except Exception as e:
        print(f"✗ Erro no banco: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Executa todos os testes"""
    print("="*70)
    print("TESTES BÁSICOS - ARGOS INDEX")
    print("="*70)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Funções Básicas", test_basic_functions()))
    results.append(("Banco de Dados", test_database()))
    
    print("\n" + "="*70)
    print("RESUMO")
    print("="*70)
    
    for name, result in results:
        status = "✓ PASSOU" if result else "✗ FALHOU"
        print(f"{name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, r in results if r)
    
    print(f"\nTotal: {total} | Passou: {passed} | Falhou: {total - passed}")
    
    return 0 if all(r for _, r in results) else 1

if __name__ == '__main__':
    sys.exit(main())

