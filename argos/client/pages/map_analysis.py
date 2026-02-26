"""
Página de análise de mapas — histórico de localização (Location History).

Permite selecionar um UFDR que contenha arquivo *LocationHistory*.json
(e.g. Google Takeout) e visualizar no mapa por onde a pessoa esteve e quando.

Autor: Matheus C. Pestana
"""

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(root_dir))

import streamlit as st
import pandas as pd
from argos.index.database import DatabaseManager, UFDRFile


@st.cache_resource
def get_db_manager():
    """Retorna instância do gerenciador de banco de dados (cached)."""
    db_manager = DatabaseManager()
    db_manager.create_tables()
    return db_manager


def main():
    st.title("🗺️ Análise de mapas — Histórico de localização")
    st.markdown(
        "Visualize por onde a pessoa esteve com base em arquivos **Location History** "
        "(ex.: Google Takeout: `*LocationHistory*.json` com `latitudeE7` / `longitudeE7`)."
    )
    st.markdown("---")

    db = get_db_manager()
    ids_with_locations = db.get_ufdr_ids_with_locations()

    if not ids_with_locations:
        st.warning(
            "Nenhum UFDR com histórico de localização encontrado. "
            "Processe UFDRs que contenham arquivos *LocationHistory*.json (ex.: Google Takeout)."
        )
        return

    # Monta lista (ufdr_id, label) com nome do arquivo e quantidade de pontos
    session = db.get_session()
    try:
        id_to_file = {}
        for ufdr in session.query(UFDRFile).filter(UFDRFile.id.in_([x[0] for x in ids_with_locations])).all():
            id_to_file[ufdr.id] = ufdr.filename or ufdr.id[:16]
    finally:
        session.close()

    options = [
        (ufdr_id, f"{id_to_file.get(ufdr_id, ufdr_id[:16])} — {count:,} pontos")
        for ufdr_id, count in sorted(ids_with_locations, key=lambda x: -x[1])
    ]
    indices = list(range(len(options)))
    choice = st.selectbox(
        "Selecione o UFDR para visualizar no mapa",
        indices,
        format_func=lambda i: options[i][1],
        key="map_ufdr_select",
    )
    selected_ufdr_id = options[choice][0]

    points = db.get_location_points(selected_ufdr_id)
    if not points:
        st.warning("Nenhum ponto de localização para este UFDR.")
        return

    # DataFrame para st.map: colunas 'lat' e 'lon'
    map_df = pd.DataFrame(
        [(p[0], p[1]) for p in points],
        columns=["lat", "lon"],
    )

    # Estatísticas
    with_timestamp = [p[2] for p in points if p[2] is not None]
    if with_timestamp:
        min_ts = min(with_timestamp)
        max_ts = max(with_timestamp)
        st.info(
            f"**{len(points):,}** pontos | "
            f"Com data/hora: **{len(with_timestamp):,}** | "
            f"Período: **{min_ts.strftime('%d/%m/%Y %H:%M')}** a **{max_ts.strftime('%d/%m/%Y %H:%M')}**"
        )
    else:
        st.info(f"**{len(points):,}** pontos (sem data/hora associada)")

    st.map(map_df, width="stretch")

    # Amostra de pontos com "quando"
    st.markdown("---")
    st.subheader("Amostra dos pontos (data/hora)")
    if with_timestamp:
        sample_size = min(500, len(points))
        sample = []
        step = max(1, len(points) // sample_size)
        for i in range(0, len(points), step):
            if len(sample) >= sample_size:
                break
            lat, lon, pt_at = points[i]
            sample.append({
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "quando": pt_at.strftime("%d/%m/%Y %H:%M:%S") if pt_at else "—",
            })
        st.dataframe(pd.DataFrame(sample), width="stretch", hide_index=True)
    else:
        st.caption("Os pontos deste UFDR não possuem data/hora no arquivo de origem.")


if __name__ == "__main__":
    main()
