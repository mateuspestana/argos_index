"""
Página de busca textual
"""

import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para imports
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(root_dir))

import streamlit as st
from argos.index.database import DatabaseManager, UFDRFile, TextEntry


@st.cache_resource
def get_db_manager():
    """Retorna instância do gerenciador de banco de dados (cached)"""
    db_manager = DatabaseManager()
    # Garante que as tabelas existam
    db_manager.create_tables()
    return db_manager


def main():
    """Página de busca textual"""
    # Header
    st.title("🔍 Busca Textual Livre")
    st.markdown("Busque por qualquer texto no corpus indexado.")
    st.markdown("---")
    
    db_manager = get_db_manager()
    
    # Campo de busca
    search_query = st.text_input("Digite sua busca:", placeholder="Ex: email, telefone, documento...")
    
    # Filtro por UFDR - Query direta para garantir dados atualizados
    from argos.index.database import UFDRFile
    session = db_manager.get_session()
    try:
        session.expire_all()
        ufdr_files = session.query(UFDRFile).order_by(UFDRFile.processed_at.desc()).all()
    finally:
        session.close()
    
    ufdr_options = ["Todos"] + [f"{ufdr.filename} ({ufdr.id[:8]}...)" for ufdr in ufdr_files]
    selected_ufdr = st.selectbox("Filtrar por UFDR:", ufdr_options)
    
    # Paginação
    if "text_search_page" not in st.session_state:
        st.session_state.text_search_page = 1
    
    items_per_page = st.selectbox("Resultados por página:", [10, 25, 50, 100], index=1)
    
    if st.button("Buscar", type="primary"):
        if search_query:
            with st.spinner("Buscando..."):
                results = search_text(db_manager, search_query, selected_ufdr, ufdr_files)
                st.session_state.text_search_results = results
                st.session_state.text_search_page = 1
                
                if results:
                    st.success(f"Encontrados {len(results)} resultados")
                else:
                    st.info("Nenhum resultado encontrado.")
        else:
            st.warning("Digite um termo de busca.")
    
    # Exibe resultados paginados
    if "text_search_results" in st.session_state and st.session_state.text_search_results:
        results = st.session_state.text_search_results
        total_pages = (len(results) + items_per_page - 1) // items_per_page
        
        # Controles de paginação
        col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
        with col1:
            if st.button("⏮️ Primeira", disabled=st.session_state.text_search_page == 1):
                st.session_state.text_search_page = 1
                st.rerun()
        with col2:
            if st.button("◀️ Anterior", disabled=st.session_state.text_search_page == 1):
                st.session_state.text_search_page -= 1
                st.rerun()
        with col3:
            st.markdown(f"**Página {st.session_state.text_search_page} de {total_pages}**")
        with col4:
            if st.button("Próxima ▶️", disabled=st.session_state.text_search_page >= total_pages):
                st.session_state.text_search_page += 1
                st.rerun()
        with col5:
            if st.button("Última ⏭️", disabled=st.session_state.text_search_page >= total_pages):
                st.session_state.text_search_page = total_pages
                st.rerun()
        
        # Exibe resultados da página atual
        start_idx = (st.session_state.text_search_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_results = results[start_idx:end_idx]
        
        st.markdown("---")
        for idx, result in enumerate(page_results, start=start_idx + 1):
            with st.expander(f"Resultado {idx} - {result['source_path'] or 'N/A'}"):
                st.write(f"**UFDR:** {result['ufdr_filename']}")
                st.write(f"**Caminho:** {result['source_path'] or 'N/A'}")
                st.write(f"**Data:** {result['indexed_at']}")
                st.markdown("---")
                st.text_area("Conteúdo:", result['content'], height=200, key=f"content_{idx}", disabled=True)


def search_text(
    db_manager: DatabaseManager,
    query: str,
    selected_ufdr: str,
    ufdr_files: list[UFDRFile]
) -> list[dict]:
    """Realiza busca textual"""
    session = db_manager.get_session()
    try:
        # Filtra por UFDR se selecionado
        ufdr_filter = None
        if selected_ufdr != "Todos":
            # Extrai ID do UFDR selecionado
            for ufdr in ufdr_files:
                if f"{ufdr.filename} ({ufdr.id[:8]}...)" == selected_ufdr:
                    ufdr_filter = ufdr.id
                    break
        
        # Busca usando LIKE (SQLite) ou FULLTEXT (MySQL)
        if ufdr_filter:
            results = session.query(TextEntry).filter(
                TextEntry.ufdr_id == ufdr_filter,
                TextEntry.content.like(f"%{query}%")
            ).all()
        else:
            results = session.query(TextEntry).filter(
                TextEntry.content.like(f"%{query}%")
            ).limit(1000).all()
        
        # Formata resultados
        formatted_results = []
        for result in results:
            ufdr = session.query(UFDRFile).filter_by(id=result.ufdr_id).first()
            formatted_results.append({
                'content': result.content,
                'source_path': result.source_path,
                'ufdr_filename': ufdr.filename if ufdr else 'N/A',
                'indexed_at': result.indexed_at.strftime("%Y-%m-%d %H:%M:%S") if result.indexed_at else 'N/A'
            })
        
        return formatted_results
    finally:
        session.close()


if __name__ == "__main__":
    main()

