import json
import subprocess
import sys
import time

import duckdb
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import lab.research.housing_reality.manifest  # noqa: F401 — populates registry

from lab.enums.uf import UF
from lab.research.housing_reality.params import HousingRealityParams
from lab.research.housing_reality.pipeline.runner import find_local_results

st.set_page_config(page_title="Research Lab", layout="wide")

_SOURCE_LABELS = {
    "census_2010": "Censo Demográfico 2010",
    "pnadc_visita1": "PNADC Anual Visita 1",
}
_UFS = [uf.value for uf in UF]

# ── Session state ──────────────────────────────────────────────────────────────

if "collect_proc" not in st.session_state:
    st.session_state.collect_proc = None

# ── Helpers ────────────────────────────────────────────────────────────────────

def _collecting() -> bool:
    proc = st.session_state.collect_proc
    if proc is None:
        return False
    if proc.poll() is not None:
        st.session_state.collect_proc = None
        return False
    return True


def _start_collection(params: HousingRealityParams) -> None:
    payload = json.dumps({
        "manifest": "lab.research.housing_reality.manifest:HousingRealityResearch",
        "params": params.model_dump(mode="json"),
    }).encode()
    proc = subprocess.Popen(
        [sys.executable, "-m", "lab.ui._pipeline_runner"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    proc.stdin.write(payload)
    proc.stdin.close()
    st.session_state.collect_proc = proc


def _save(params: HousingRealityParams, local: dict) -> None:
    from lab.infrastructure.research.duckdb_repository import make_repository
    repo = make_repository()
    items = [(uf, ft, path) for uf, files in local.items() for ft, path in files.items()]
    bar = st.progress(0, text="Conectando…")
    status = st.empty()
    for idx, (uf, ft, path) in enumerate(items):
        status.caption(f"Salvando {uf}/{ft} ({idx + 1}/{len(items)})…")
        repo.save("housing_reality", uf, ft, path)
        bar.progress((idx + 1) / len(items))
    bar.empty()
    status.empty()
    st.success("Salvo!")


# ── Header: Form ───────────────────────────────────────────────────────────────

st.title("Research Lab")

col1, col2, col3 = st.columns([2, 3, 1])
with col1:
    source = st.selectbox(
        "Pesquisa",
        list(_SOURCE_LABELS.keys()),
        format_func=_SOURCE_LABELS.get,
    )
with col2:
    selected_ufs = st.multiselect("UFs", _UFS, placeholder="Todas")
with col3:
    st.write("")  # vertical alignment
    searched = st.button("Pesquisar", type="primary", use_container_width=True)

params = HousingRealityParams(
    source=source,
    ufs=[UF(u) for u in selected_ufs] or None,
)

# ── Body: Results ──────────────────────────────────────────────────────────────

local = find_local_results(params)

if local:
    viz = st.radio("Visualização", ["Tabela", "Gráfico"], horizontal=True)

    if viz == "Tabela":
        file_types = sorted({ft for files in local.values() for ft in files})
        selected_fts = st.multiselect("Arquivos", file_types, default=file_types)
        limit = st.slider("Linhas por arquivo", 100, 2000, 500, step=100)

        for ft in selected_fts:
            st.subheader(ft)
            for uf, files in sorted(local.items()):
                path = files.get(ft)
                if not path:
                    continue
                st.caption(uf)
                df = duckdb.execute(f"SELECT * FROM read_parquet('{path}') LIMIT {limit}").df()
                st.dataframe(df, use_container_width=True)

    else:
        counts: dict[str, int] = {}
        for uf, files in local.items():
            path = files.get("domicilios") or files.get("moradores")
            if path:
                n = duckdb.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[0]
                counts[uf] = n
        if counts:
            df_chart = pd.DataFrame.from_dict(counts, orient="index", columns=["Registros"])
            st.bar_chart(df_chart, x_label="UF", y_label="Registros")
        else:
            st.warning("Nenhum arquivo de referência disponível para as UFs selecionadas.")

elif searched:
    st.info("Nenhum dado local. Use **Coletar** abaixo para iniciar a coleta.")

# ── Footer: Actions ────────────────────────────────────────────────────────────

st.divider()
fcol1, fcol2, _ = st.columns([1, 1, 4])

collecting = _collecting()

with fcol1:
    if collecting:
        st.info("⟳ Coletando em background…")
    else:
        label = "Coletar mais" if local else "Coletar"
        if st.button(label, use_container_width=True):
            _start_collection(params)
            st.rerun()

with fcol2:
    if local and st.button("Salvar", use_container_width=True):
        _save(params, local)

if collecting:
    time.sleep(2)
    st.rerun()
