#!/usr/bin/env python3
"""
Script para resetar/zerar o banco de dados do Argos Index
"""

import sys
from pathlib import Path

# Adiciona diretório ao path
sys.path.insert(0, '.')

from argos.config import SQLITE_DB_PATH, PROJECT_ROOT
from argos.index.database import DatabaseManager

def reset_database():
    """Reseta o banco de dados, removendo todos os dados"""
    
    db_path = Path(SQLITE_DB_PATH)
    
    print("=" * 60)
    print("Argos Index - Reset do Banco de Dados")
    print("=" * 60)
    print()
    
    # Verifica se o banco existe
    if not db_path.exists():
        print(f"⚠️  Banco de dados não encontrado em: {db_path}")
        print("   Nada a fazer.")
        return
    
    # Mostra informações do banco
    size_mb = db_path.stat().st_size / (1024 * 1024)
    print(f"📁 Banco de dados: {db_path.absolute()}")
    print(f"📊 Tamanho: {size_mb:.2f} MB")
    print()
    
    # Conta registros antes de deletar
    try:
        db_manager = DatabaseManager()
        from argos.index.database import UFDRFile, TextEntry, RegexHit
        from sqlalchemy import func
        
        session = db_manager.get_session()
        try:
            ufdr_count = session.query(func.count(UFDRFile.id)).scalar()
            text_count = session.query(func.count(TextEntry.id)).scalar()
            hits_count = session.query(func.count(RegexHit.id)).scalar()
            
            print(f"📊 Registros atuais:")
            print(f"   - UFDRs: {ufdr_count}")
            print(f"   - Text Entries: {text_count}")
            print(f"   - Regex Hits: {hits_count}")
            print()
        finally:
            session.close()
    except Exception as e:
        print(f"⚠️  Não foi possível contar registros: {e}")
        print()
    
    # Confirmação
    print("⚠️  ATENÇÃO: Esta operação irá DELETAR TODOS os dados!")
    resposta = input("   Deseja continuar? (digite 'SIM' para confirmar): ")
    
    if resposta.upper() != 'SIM':
        print("❌ Operação cancelada.")
        return
    
    # Deleta o arquivo
    try:
        db_path.unlink()
        print(f"✅ Banco de dados deletado: {db_path}")
    except Exception as e:
        print(f"❌ Erro ao deletar banco de dados: {e}")
        return
    
    # Recria o banco vazio
    try:
        print()
        print("🔄 Recriando banco de dados vazio...")
        db_manager = DatabaseManager()
        db_manager.create_tables()
        print("✅ Banco de dados recriado com sucesso!")
        print()
        print("📝 O banco está agora vazio e pronto para uso.")
    except Exception as e:
        print(f"❌ Erro ao recriar banco de dados: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    print("=" * 60)
    print("Reset concluído!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        reset_database()
    except KeyboardInterrupt:
        print("\n\n❌ Operação cancelada pelo usuário.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

