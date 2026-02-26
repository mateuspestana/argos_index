"""
Página de busca textual
"""

import os
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para imports
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(root_dir))

import streamlit as st
from sqlalchemy import or_

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
    
    # Campo de busca (texto ou MD5 do arquivo)
    search_query = st.text_input(
        "Digite sua busca:",
        placeholder="Ex: email, telefone, documento... ou MD5 do arquivo (32 caracteres hex)",
        help="Busca no conteúdo do texto e também pelo MD5 do arquivo interno."
    )
    
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
            expander_label = result.get('source_name') or result.get('source_path') or 'N/A'
            with st.expander(f"Resultado {idx} - {expander_label}"):
                st.write(f"**Nome do arquivo:** {result.get('source_name') or result.get('source_path') or 'N/A'}")
                st.write(f"**MD5 do arquivo:** {result.get('file_md5', 'N/A')}")
                st.write(f"**Caminho completo do arquivo (interno):** {result.get('full_source_path') or result.get('source_path') or 'N/A'}")
                st.write(f"**Caminho completo do UFDR:** {result.get('ufdr_full_path') or 'N/A'}")
                st.write(f"**UFDR (nome):** {result['ufdr_filename']}")
                st.write(f"**Caminho interno no UFDR:** {result['source_path'] or 'N/A'}")
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
        
        # Busca no conteúdo e no MD5 do arquivo (LIKE em ambos)
        text_or_md5 = or_(
            TextEntry.content.like(f"%{query}%"),
            TextEntry.file_md5.like(f"%{query}%")
        )
        if ufdr_filter:
            results = session.query(TextEntry).filter(
                TextEntry.ufdr_id == ufdr_filter,
                text_or_md5
            ).all()
        else:
            results = session.query(TextEntry).filter(text_or_md5).limit(1000).all()
        
        formatted_results = []
        for result in results:
            ufdr = session.query(UFDRFile).filter_by(id=result.ufdr_id).first()
            ufdr_full_path = getattr(ufdr, 'full_path', None) if ufdr else None
            if not ufdr_full_path and ufdr and ufdr.source and ufdr.filename:
                ufdr_full_path = os.path.join(ufdr.source, ufdr.filename)
            formatted_results.append({
                'content': result.content,
                'source_path': result.source_path,
                'source_name': getattr(result, 'source_name', None),
                'full_source_path': getattr(result, 'full_source_path', None),
                'file_md5': getattr(result, 'file_md5', None) or 'N/A',
                'ufdr_filename': ufdr.filename if ufdr else 'N/A',
                'ufdr_full_path': ufdr_full_path or 'N/A',
                'indexed_at': result.indexed_at.strftime("%Y-%m-%d %H:%M:%S") if result.indexed_at else 'N/A'
            })

        return formatted_results
    finally:
        session.close()


if __name__ == "__main__":
    main()

