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

from lab.platform.research.registry import get_registry

st.set_page_config(page_title="Research Lab", layout="wide")

# ── Session state ──────────────────────────────────────────────────────────────

if "view" not in st.session_state:
    st.session_state.view = "catalog"
if "manifest_id" not in st.session_state:
    st.session_state.manifest_id = None
if "collect_procs" not in st.session_state:
    st.session_state.collect_procs = {}  # manifest_id → Popen

registry = get_registry()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _local(manifest_cls) -> dict | None:
    return manifest_cls.local_results(manifest_cls.params_model())


def _start_collection(manifest_cls) -> None:
    payload = json.dumps({
        "manifest": f"{manifest_cls.__module__}:{manifest_cls.__qualname__}",
        "params": manifest_cls.params_model().model_dump(mode="json"),
    }).encode()
    proc = subprocess.Popen(
        [sys.executable, "-m", "lab.ui._pipeline_runner"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    proc.stdin.write(payload)
    proc.stdin.close()
    st.session_state.collect_procs[manifest_cls.id] = proc


# ── Catalog ────────────────────────────────────────────────────────────────────

def view_catalog() -> None:
    st.title("Research Lab")

    # Check finished collections
    for mid, proc in list(st.session_state.collect_procs.items()):
        if proc.poll() is not None:
            del st.session_state.collect_procs[mid]

    cols = st.columns(3, gap="large")
    for i, (manifest_id, manifest_cls) in enumerate(registry.items()):
        with cols[i % 3]:
            local = _local(manifest_cls)
            collecting = manifest_id in st.session_state.collect_procs

            with st.container(border=True):
                st.subheader(manifest_cls.name)
                st.caption(manifest_cls.description)

                if collecting:
                    st.info("⟳ Coletando em background…")
                elif local:
                    ufs = sorted(local.keys())
                    all_key = f"all_ufs_{manifest_id}"
                    todas = st.checkbox("Todas as UFs", value=True, key=all_key)
                    if todas:
                        selected = ufs
                        st.caption(f"{len(ufs)} UF(s) coletadas")
                    else:
                        selected = st.multiselect("UFs", ufs, default=ufs, key=f"ufs_{manifest_id}")
                        if not selected:
                            selected = ufs
                    st.session_state[f"selected_ufs_{manifest_id}"] = selected

                c1, c2 = st.columns(2)
                with c1:
                    if local and st.button("Visualizar", key=f"v_{manifest_id}", type="primary", use_container_width=True):
                        st.session_state.view = "explore"
                        st.session_state.manifest_id = manifest_id
                        st.rerun()
                with c2:
                    label = "Coletar mais" if local else "Coletar"
                    if not collecting and st.button(label, key=f"c_{manifest_id}", use_container_width=True):
                        _start_collection(manifest_cls)
                        st.rerun()

    if st.session_state.collect_procs:
        time.sleep(2)
        st.rerun()


# ── Explore ────────────────────────────────────────────────────────────────────

def view_explore() -> None:
    manifest_id = st.session_state.manifest_id
    manifest_cls = registry.get(manifest_id)

    if st.button("← Catálogo"):
        st.session_state.view = "catalog"
        st.rerun()

    if not manifest_cls:
        return

    local = _local(manifest_cls)
    if not local:
        st.warning("Nenhum dado local disponível. Colete primeiro no catálogo.")
        return

    st.title(manifest_cls.name)

    with st.sidebar:
        st.header("Filtros")
        ufs_available = sorted(local.keys())
        preselected = st.session_state.get(f"selected_ufs_{manifest_id}", ufs_available)
        selected_ufs = st.multiselect("UFs", ufs_available, default=preselected)
        viz = st.radio("Visualização", ["Tabela", "Gráfico"])
        if viz == "Tabela":
            sample_files = sorted(next(iter(local.values())).keys())
            selected_files = st.multiselect("Arquivos", sample_files, default=sample_files)
            limit = st.slider("Linhas por arquivo", 100, 2000, 500, step=100)

    if not selected_ufs:
        st.info("Selecione pelo menos uma UF.")
        return

    if viz == "Tabela":
        if not selected_files:
            st.info("Selecione pelo menos um arquivo.")
        else:
            for file_type in selected_files:
                st.header(file_type)
                for uf in selected_ufs:
                    path = local.get(uf, {}).get(file_type)
                    if not path:
                        continue
                    st.subheader(uf)
                    df = duckdb.execute(f"SELECT * FROM read_parquet('{path}') LIMIT {limit}").df()
                    st.dataframe(df, use_container_width=True)

    else:
        counts: dict[str, int] = {}
        for uf in selected_ufs:
            path = local.get(uf, {}).get("domicilios")
            if path:
                n = duckdb.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[0]
                counts[uf] = n

        if counts:
            df_chart = pd.DataFrame.from_dict(counts, orient="index", columns=["Domicílios"])
            st.bar_chart(df_chart, x_label="UF", y_label="Domicílios")
        else:
            st.warning("Arquivo 'domicilios' não disponível para as UFs selecionadas.")


# ── Router ─────────────────────────────────────────────────────────────────────

if st.session_state.view == "catalog":
    view_catalog()
elif st.session_state.view == "explore":
    view_explore()
