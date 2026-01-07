"""
Página de lista de UFDRs processados
"""

import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para imports
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(root_dir))

import streamlit as st
import pandas as pd
from argos.index.database import DatabaseManager


@st.cache_resource
def get_db_manager():
    """Retorna instância do gerenciador de banco de dados (cached)"""
    db_manager = DatabaseManager()
    # Garante que as tabelas existam
    db_manager.create_tables()
    return db_manager


def main():
    """Página de lista de UFDRs processados"""
    # Header
    st.title("📁 UFDRs Processados")
    
    # Botão de refresh
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Atualizar", help="Recarrega os dados do banco"):
            # Limpa cache e força rerun
            if hasattr(st.session_state, 'ufdr_list_page'):
                del st.session_state.ufdr_list_page
            st.cache_resource.clear()
            st.rerun()
    
    st.markdown("---")
    
    db_manager = get_db_manager()
    # Força uma nova query sem cache
    session = db_manager.get_session()
    try:
        # Expira cache e força refresh
        session.expire_all()
        # Query direta para garantir dados frescos
        from argos.index.database import UFDRFile
        from sqlalchemy import func
        
        # Primeiro verifica se há dados
        count = session.query(func.count(UFDRFile.id)).scalar()
        if count == 0:
            st.warning("⚠️ Nenhum UFDR processado ainda. Execute o worker para processar arquivos UFDR.")
            return
        
        ufdr_files = session.query(UFDRFile).order_by(UFDRFile.processed_at.desc()).all()
    finally:
        session.close()
    
    if ufdr_files:
        st.info(f"Total de {len(ufdr_files)} UFDR(s) processado(s)")
        
        # Paginação
        if "ufdr_list_page" not in st.session_state:
            st.session_state.ufdr_list_page = 1
        
        items_per_page = st.selectbox("Resultados por página:", [10, 25, 50, 100], index=1)
        total_pages = (len(ufdr_files) + items_per_page - 1) // items_per_page
        
        # Controles de paginação
        col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
        with col1:
            if st.button("⏮️ Primeira", disabled=st.session_state.ufdr_list_page == 1, key="first_ufdr"):
                st.session_state.ufdr_list_page = 1
                st.rerun()
        with col2:
            if st.button("◀️ Anterior", disabled=st.session_state.ufdr_list_page == 1, key="prev_ufdr"):
                st.session_state.ufdr_list_page -= 1
                st.rerun()
        with col3:
            st.markdown(f"**Página {st.session_state.ufdr_list_page} de {total_pages}**")
        with col4:
            if st.button("Próxima ▶️", disabled=st.session_state.ufdr_list_page >= total_pages, key="next_ufdr"):
                st.session_state.ufdr_list_page += 1
                st.rerun()
        with col5:
            if st.button("Última ⏭️", disabled=st.session_state.ufdr_list_page >= total_pages, key="last_ufdr"):
                st.session_state.ufdr_list_page = total_pages
                st.rerun()
        
        # Exibe resultados da página atual
        start_idx = (st.session_state.ufdr_list_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_ufdrs = ufdr_files[start_idx:end_idx]
        
        # Cria DataFrame
        df = pd.DataFrame([{
            'ID (Hash)': ufdr.id[:16] + "...",
            'Nome do Arquivo': ufdr.filename,
            'Origem': ufdr.source or 'N/A',
            'Status': ufdr.status,
            'Processado em': ufdr.processed_at.strftime("%Y-%m-%d %H:%M:%S") if ufdr.processed_at else 'N/A'
        } for ufdr in page_ufdrs])
        
        st.dataframe(df, width='stretch', hide_index=True)
    else:
        st.warning("Nenhum UFDR processado ainda.")


if __name__ == "__main__":
    main()

