"""
Página de busca por entidades
"""

import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para imports
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(root_dir))

import streamlit as st
import pandas as pd
from datetime import datetime
from argos.index.database import DatabaseManager, UFDRFile, RegexHit
from argos.index.regex_engine import RegexEngine


@st.cache_resource
def get_db_manager():
    """Retorna instância do gerenciador de banco de dados (cached)"""
    db_manager = DatabaseManager()
    # Garante que as tabelas existam
    db_manager.create_tables()
    return db_manager


@st.cache_resource
def get_regex_engine():
    """Retorna instância do motor de regex (cached)"""
    return RegexEngine()


def main():
    """Página de busca por entidades"""
    # Header
    st.title("🔎 Busca por Entidades")
    st.markdown("Busque por tipos específicos de entidades extraídas (CPF, email, crypto, etc.)")
    st.markdown("---")
    
    db_manager = get_db_manager()
    regex_engine = get_regex_engine()
    
    # Seleção de tipo
    pattern_names = regex_engine.get_pattern_names()
    selected_type = st.selectbox("Tipo de entidade:", ["Todos"] + pattern_names)
    
    # Campo de valor (opcional)
    value_filter = st.text_input("Filtrar por valor (opcional):", placeholder="Ex: 123.456.789-00")
    
    # Filtro por validação
    validation_filter = st.selectbox("Filtrar por validação:", ["Todos", "Válidos", "Inválidos"])
    
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
    if "entity_search_page" not in st.session_state:
        st.session_state.entity_search_page = 1
    
    items_per_page = st.selectbox("Resultados por página:", [25, 50, 100, 200], index=1)
    
    if st.button("Buscar Entidades", type="primary"):
        with st.spinner("Buscando..."):
            results = search_entities(
                db_manager, selected_type, value_filter,
                validation_filter, selected_ufdr, ufdr_files
            )
            st.session_state.entity_search_results = results
            st.session_state.entity_search_page = 1
            
            if results:
                st.success(f"Encontrados {len(results)} resultados")
            else:
                st.info("Nenhum resultado encontrado.")
    
    # Exibe resultados paginados
    if "entity_search_results" in st.session_state and st.session_state.entity_search_results:
        results = st.session_state.entity_search_results
        total_pages = (len(results) + items_per_page - 1) // items_per_page
        
        # Controles de paginação
        col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
        with col1:
            if st.button("⏮️ Primeira", disabled=st.session_state.entity_search_page == 1, key="first_entity"):
                st.session_state.entity_search_page = 1
                st.rerun()
        with col2:
            if st.button("◀️ Anterior", disabled=st.session_state.entity_search_page == 1, key="prev_entity"):
                st.session_state.entity_search_page -= 1
                st.rerun()
        with col3:
            st.markdown(f"**Página {st.session_state.entity_search_page} de {total_pages}**")
        with col4:
            if st.button("Próxima ▶️", disabled=st.session_state.entity_search_page >= total_pages, key="next_entity"):
                st.session_state.entity_search_page += 1
                st.rerun()
        with col5:
            if st.button("Última ⏭️", disabled=st.session_state.entity_search_page >= total_pages, key="last_entity"):
                st.session_state.entity_search_page = total_pages
                st.rerun()
        
        # Exibe resultados da página atual
        start_idx = (st.session_state.entity_search_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_results = results[start_idx:end_idx]
        
        # Cria DataFrame para exibição
        df = pd.DataFrame(page_results)
        st.dataframe(df, width='stretch', hide_index=True)
        
        # Botão de exportação (exporta todos os resultados, não só a página)
        csv = pd.DataFrame(results).to_csv(index=False)
        st.download_button(
            label="📥 Exportar Todos os Resultados para CSV",
            data=csv,
            file_name=f"entidades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )


def search_entities(
    db_manager: DatabaseManager,
    entity_type: str,
    value_filter: str,
    validation_filter: str,
    selected_ufdr: str,
    ufdr_files: list[UFDRFile]
) -> list[dict]:
    """Realiza busca por entidades"""
    session = db_manager.get_session()
    try:
        query = session.query(RegexHit)
        
        # Filtro por tipo
        if entity_type != "Todos":
            query = query.filter(RegexHit.type == entity_type)
        
        # Filtro por valor
        if value_filter:
            query = query.filter(RegexHit.value.like(f"%{value_filter}%"))
        
        # Filtro por validação
        if validation_filter == "Válidos":
            query = query.filter(RegexHit.validated == True)
        elif validation_filter == "Inválidos":
            query = query.filter(RegexHit.validated == False)
        
        # Filtro por UFDR
        if selected_ufdr != "Todos":
            for ufdr in ufdr_files:
                if f"{ufdr.filename} ({ufdr.id[:8]}...)" == selected_ufdr:
                    query = query.filter(RegexHit.ufdr_id == ufdr.id)
                    break
        
        results = query.limit(5000).all()
        
        # Formata resultados
        formatted_results = []
        for result in results:
            ufdr = session.query(UFDRFile).filter_by(id=result.ufdr_id).first()
            formatted_results.append({
                'Tipo': result.type,
                'Valor': result.value,
                'Validado': 'Sim' if result.validated else 'Não',
                'UFDR': ufdr.filename if ufdr else 'N/A',
                'Contexto': result.context[:100] + "..." if result.context and len(result.context) > 100 else result.context or 'N/A'
            })
        
        return formatted_results
    finally:
        session.close()


if __name__ == "__main__":
    main()

