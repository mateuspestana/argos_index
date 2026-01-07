"""
Página de estatísticas
"""

import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para imports
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(root_dir))

import streamlit as st
import pandas as pd
from argos.index.database import DatabaseManager, UFDRFile, TextEntry, RegexHit
from argos.index.regex_engine import RegexEngine
from sqlalchemy import func


@st.cache_resource
def get_db_manager():
    """Retorna instância do gerenciador de banco de dados (cached)"""
    db_manager = DatabaseManager()
    # Garante que as tabelas existam
    db_manager.create_tables()
    return db_manager

def get_fresh_session():
    """Retorna uma sessão fresca do banco (não cacheada)"""
    db_manager = get_db_manager()
    return db_manager.get_session()


@st.cache_resource
def get_regex_engine():
    """Retorna instância do motor de regex (cached)"""
    return RegexEngine()


def main():
    """Página de estatísticas"""
    # Header
    st.title("📊 Estatísticas do Sistema")
    
    # Botão de refresh
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Atualizar", help="Recarrega os dados do banco"):
            st.cache_resource.clear()
            st.rerun()
    
    st.markdown("---")
    
    db_manager = get_db_manager()
    regex_engine = get_regex_engine()
    
    # Usa sessão fresca para garantir dados atualizados
    session = db_manager.get_session()
    try:
        # Expira cache da sessão
        session.expire_all()
        # Estatísticas gerais
        col1, col2, col3 = st.columns(3)
        
        # Usa func.count() para garantir query fresca
        total_ufdrs = session.query(func.count(UFDRFile.id)).scalar() or 0
        total_text_entries = session.query(func.count(TextEntry.id)).scalar() or 0
        total_regex_hits = session.query(func.count(RegexHit.id)).scalar() or 0
        
        col1.metric("UFDRs Processados", total_ufdrs)
        col2.metric("Entradas de Texto", total_text_entries)
        col3.metric("Hits de Regex", total_regex_hits)
        
        st.markdown("---")
        
        # Estatísticas por tipo de regex
        st.subheader("Hits por Tipo de Entidade")
        hits_by_type = session.query(
            RegexHit.type,
            func.count(RegexHit.id).label('count')
        ).group_by(RegexHit.type).order_by(func.count(RegexHit.id).desc()).all()
        
        if hits_by_type:
            df_type = pd.DataFrame([{'Tipo': t, 'Quantidade': c} for t, c in hits_by_type])
            st.bar_chart(df_type.set_index('Tipo'))
            st.dataframe(df_type, width='stretch', hide_index=True)
        
        # Estatísticas de validação
        st.markdown("---")
        st.subheader("Validação de Documentos")
        
        validated_count = session.query(func.count(RegexHit.id)).filter(RegexHit.validated == True).scalar() or 0
        invalidated_count = session.query(func.count(RegexHit.id)).filter(RegexHit.validated == False).scalar() or 0
        
        col1, col2 = st.columns(2)
        col1.metric("Documentos Válidos", validated_count)
        col2.metric("Documentos Inválidos", invalidated_count)
        
    finally:
        session.close()


if __name__ == "__main__":
    main()

