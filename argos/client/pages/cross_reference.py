"""
Página de cruzamentos - Informações repetidas entre arquivos (ex.: mesmo CPF em vários UFDRs)
"""

import os
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(root_dir))

import streamlit as st
import pandas as pd
from sqlalchemy import distinct, func

from argos.index.database import DatabaseManager, UFDRFile, RegexHit
from argos.index.regex_engine import RegexEngine


@st.cache_resource
def get_db_manager():
    """Retorna instância do gerenciador de banco de dados (cached)"""
    db_manager = DatabaseManager()
    db_manager.create_tables()
    return db_manager


@st.cache_resource
def get_regex_engine():
    """Retorna instância do motor de regex (cached)"""
    return RegexEngine()


def get_cross_reference_rows(db_manager, type_filter):
    """
    Valores (ex.: CPF) que aparecem em mais de um UFDR.
    Retorna lista de dict com type, value, ufdr_count, ufdr_ids.
    """
    session = db_manager.get_session()
    try:
        session.expire_all()
        q = (
            session.query(
                RegexHit.type,
                RegexHit.value,
                func.count(distinct(RegexHit.ufdr_id)).label("ufdr_count"),
            )
            .group_by(RegexHit.type, RegexHit.value)
            .having(func.count(distinct(RegexHit.ufdr_id)) > 1)
        )
        if type_filter and type_filter != "Todos":
            q = q.filter(RegexHit.type == type_filter)
        rows = q.all()
        result = []
        for type_name, value, ufdr_count in rows:
            ufdr_ids = (
                session.query(RegexHit.ufdr_id)
                .filter(RegexHit.type == type_name, RegexHit.value == value)
                .distinct()
                .all()
            )
            ufdr_ids = [x[0] for x in ufdr_ids]
            result.append({
                "type": type_name,
                "value": value,
                "ufdr_count": ufdr_count,
                "ufdr_ids": ufdr_ids,
            })
        return result
    finally:
        session.close()


def get_ufdr_details_for_value(db_manager, type_name, value):
    """Para um (type, value), retorna lista de UFDRs com nome e caminho completo."""
    session = db_manager.get_session()
    try:
        session.expire_all()
        hits = (
            session.query(RegexHit)
            .filter(RegexHit.type == type_name, RegexHit.value == value)
            .all()
        )
        ufdr_ids_seen = set()
        out = []
        for h in hits:
            if h.ufdr_id in ufdr_ids_seen:
                continue
            ufdr_ids_seen.add(h.ufdr_id)
            ufdr = session.query(UFDRFile).filter_by(id=h.ufdr_id).first()
            full_path = getattr(ufdr, "full_path", None) if ufdr else None
            if not full_path and ufdr and ufdr.source and ufdr.filename:
                full_path = os.path.join(ufdr.source, ufdr.filename)
            out.append({
                "ufdr_id": h.ufdr_id,
                "filename": ufdr.filename if ufdr else "N/A",
                "full_path": full_path or "N/A",
            })
        return out
    finally:
        session.close()


def main():
    st.title("Cruzamentos entre informações")
    st.markdown(
        "Valores (ex.: CPF, CNPJ) que aparecem em **mais de um arquivo UFDR**. "
        "Útil para mensurar informações repetidas entre fontes."
    )
    st.markdown("---")

    db_manager = get_db_manager()
    regex_engine = get_regex_engine()
    pattern_names = regex_engine.get_pattern_names()

    type_filter = st.selectbox(
        "Filtrar por tipo de entidade:",
        ["Todos"] + pattern_names,
        key="cross_ref_type",
    )

    if st.button("Atualizar cruzamentos", type="primary"):
        st.session_state.cross_ref_data = get_cross_reference_rows(db_manager, type_filter)
        st.session_state.cross_ref_type_filter = type_filter

    if "cross_ref_data" not in st.session_state:
        st.session_state.cross_ref_data = get_cross_reference_rows(db_manager, type_filter)
        st.session_state.cross_ref_type_filter = type_filter

    rows = st.session_state.cross_ref_data
    if not rows:
        st.info("Nenhum valor encontrado em mais de um UFDR (ou nenhum dado indexado).")
        return

    total_repeated = len(rows)
    st.metric("Valores que aparecem em mais de um UFDR", total_repeated)
    st.markdown("---")

    df = pd.DataFrame([
        {"Tipo": r["type"], "Valor": r["value"], "Nº de UFDRs": r["ufdr_count"]}
        for r in rows
    ])
    st.dataframe(df, width="stretch", hide_index=True)

    st.subheader("Detalhe por valor")
    selected_idx = st.selectbox(
        "Selecione um valor para ver em quais UFDRs aparece:",
        range(len(rows)),
        format_func=lambda i: f"{rows[i]['type']} = {rows[i]['value']} ({rows[i]['ufdr_count']} UFDRs)",
        key="cross_ref_select",
    )
    if selected_idx is not None:
        r = rows[selected_idx]
        details = get_ufdr_details_for_value(db_manager, r["type"], r["value"])
        st.write(f"**{r['type']}:** `{r['value']}` aparece em **{len(details)}** arquivo(s):")
        for d in details:
            with st.expander(f"{d['filename']} ({d['ufdr_id'][:12]}...)"):
                st.write("**Caminho completo do UFDR:**", d["full_path"])


if __name__ == "__main__":
    main()
