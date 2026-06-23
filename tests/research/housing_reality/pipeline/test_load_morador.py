from pathlib import Path

import pandas as pd
import pytest

from lab.infrastructure.database.duckdb_adapter import DuckDBAdapter
from lab.infrastructure.database.migrations import apply_migrations
from lab.research.housing_reality.pipeline.load_morador import load


def _census(work_dir: Path) -> None:
    d = work_dir / "census_2010" / "SP" / "mapped"
    d.mkdir(parents=True)
    pd.DataFrame([{
        "situacao_do_domicilio": 1, "area_de_ponderacao": 1, "controle": 100,
        "comodos_numero": 5, "comodos_como_dormitorio_numero": 2,
        "quantas_pessoas_moravam_neste_domicilio_em_31_de_julho_de_2010": 2,
        "banheiros_de_uso_exclusivo_numero": 1, "valor_do_aluguel_em_reais": 0.0,
        "rendimento_mensal_domiciliar_em_julho_de_2010": 3000.0,
        "rendimento_domiciliar_per_capita_em_julho_de_2010": 1500.0,
        "codigo_do_municipio": 355030,
    }]).to_parquet(d / "domicilios.parquet")
    pd.DataFrame([
        {"peso_amostral": 10.0, "area_de_ponderacao": 1, "controle": 100,
         "sexo": 1, "variavel_auxiliar_da_idade_calculada_em_anos": 30, "cor_ou_raca": 4},
        {"peso_amostral": 10.0, "area_de_ponderacao": 1, "controle": 100,
         "sexo": 2, "variavel_auxiliar_da_idade_calculada_em_anos": 28, "cor_ou_raca": 1},
    ]).to_parquet(d / "pessoas.parquet")


def _pnadc(work_dir: Path) -> None:
    d = work_dir / "pnadc" / "2025" / "mapped"
    d.mkdir(parents=True)
    pd.DataFrame([{
        "uf": "SP", "peso_com_calibracao": 12.0, "tipo_de_situacao_da_regiao": 1,
        "upa": 350000001, "numero_de_selecao_do_domicilio": 1, "painel": 5,
        "numero_de_comodos": 6, "numero_de_dormitorios": 2,
        "numero_de_pessoas_no_domicilio": 3,
        "numero_de_banheiros_exclusivos_dos_moradores": 2, "valor_do_aluguel_mensal": 0.0,
        "rendimento_habitual_domiciliar_mensal": 6000.0,
        "rendimento_habitual_domiciliar_per_capita_mensal": 2000.0,
        "sexo": 2, "idade_na_data_de_referencia": 40, "cor_ou_raca": 2,
    }]).to_parquet(d / "SP_moradores.parquet")


@pytest.fixture()
def db_and_data(tmp_path: Path):
    _census(tmp_path)
    _pnadc(tmp_path)
    db = DuckDBAdapter()  # in-memory
    apply_migrations(db)
    return db, tmp_path


def test_counts_per_source(db_and_data):
    db, wd = db_and_data
    assert load(db, wd) == {"census_2010": 2, "pnadc_2025": 1}


def test_harmonized_values(db_and_data):
    db, wd = db_and_data
    load(db, wd)
    row = db.query("SELECT * FROM morador WHERE fonte = 'pnadc_2025'").iloc[0]
    assert row["situacao"] == "urbana"        # tipo_de_situacao_da_regiao = 1
    assert row["sexo"] == "feminino"          # sexo = 2
    assert row["cor_raca"] == "preta"         # cor = 2
    assert row["id_domicilio"] == "350000001_1_5"  # upa_v1008_painel
    assert pd.isna(row["municipio"])          # PNADC não tem município


def test_idempotent(db_and_data):
    db, wd = db_and_data
    load(db, wd)
    load(db, wd)
    assert int(db.query("SELECT COUNT(*) c FROM morador").iloc[0]["c"]) == 3
