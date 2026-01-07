"""
Argos Index - Sistema de Extração, Indexação e Busca em Arquivos UFDR
Desenvolvido pelo GENI/UFF para a Polícia Federal
"""

import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para imports
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

import streamlit as st
from argos.index.database import DatabaseManager

# Configuração da página
st.set_page_config(
    page_title="Argos Index - UFDR Reader",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Garante que as tabelas do banco existam
@st.cache_resource
def init_database():
    """Inicializa o banco de dados criando as tabelas se necessário"""
    db_manager = DatabaseManager()
    db_manager.create_tables()
    return db_manager

# Inicializa banco na primeira execução
init_database()

# Header com informações do sistema
st.sidebar.title("🔍 Argos Index")
st.sidebar.markdown("**Sistema de Extração, Indexação e Busca em Arquivos UFDR**")
st.sidebar.markdown("---")
st.sidebar.markdown("**Desenvolvido por:**")
st.sidebar.markdown("GENI/UFF")
st.sidebar.markdown("**Em parceria com**")
st.sidebar.markdown("SR/PF/RJ")
st.sidebar.markdown("---")

# Define as páginas usando st.Page
# Caminhos relativos ao diretório raiz do projeto
pages = {
    "Busca": [
        st.Page("pages/text_search.py", title="Busca Textual", icon="🔍"),
        st.Page("pages/entity_search.py", title="Busca por Entidades", icon="🔎"),
    ],
    "Análise": [
        st.Page("pages/statistics.py", title="Estatísticas", icon="📊"),
        st.Page("pages/ufdr_list.py", title="UFDRs Processados", icon="📁"),
    ]
}

# Cria navegação
pg = st.navigation(pages)

# Executa a página selecionada
pg.run()
