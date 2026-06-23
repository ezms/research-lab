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
        "abastecimento_de_agua_forma": 1,
        "esgotamento_sanitario_tipo": 1,
        "energia_eletrica_existencia": 1,
        "geladeira_existencia": 1,
        "maquina_de_lavar_roupa_existencia": 2,
        "microcomputador_com_acesso_a_internet_existencia": 1,
        "automovel_para_uso_particular_existencia": 1,
        "motocicleta_para_uso_particular_existencia": 2,
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
        "principal_forma_de_abastecimento_de_agua": 2,
        "destino_do_esgoto_do_banheiro": 3,
        "origem_da_energia_eletrica": 1,
        "domicilio_possui_geladeira": 2,
        "domicilio_possui_maquina_de_lavar_roupa": 2,
        "acessa_a_internet": 1,
        "possui_automovel_ou_motocicleta_de_uso_pessoal": 2,
        "combustivel_mais_utilizado_na_preparacao_dos_alimentos": 1,
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
    assert row["situacao"] == "urbana"
    assert row["sexo"] == "feminino"
    assert row["cor_raca"] == "preta"
    assert row["id_domicilio"] == "350000001_1_5"
    assert pd.isna(row["municipio"])
    assert row["agua"] == "poco_artesiano"
    assert row["esgoto"] == "fossa_septica_nao_ligada"
    assert row["energia"] == "sim"
    assert row["geladeira"] == True
    assert row["maquina_lavar"] == False
    assert row["internet"] == True
    assert row["auto_moto"] == False
    assert row["combustivel_cozinha"] == "gas_botijao"


def test_census_infra_columns(db_and_data):
    db, wd = db_and_data
    load(db, wd)
    rows = db.query(
        "SELECT DISTINCT agua, esgoto, energia, geladeira, maquina_lavar, internet, auto_moto"
        " FROM morador WHERE fonte = 'census_2010'"
    )
    r = rows.iloc[0]
    assert r["agua"] == "rede_geral"
    assert r["esgoto"] == "rede_geral"
    assert r["energia"] == "sim"
    assert r["geladeira"] == True
    assert r["maquina_lavar"] == False
    assert r["internet"] == True
    assert r["auto_moto"] == True


def test_idempotent(db_and_data):
    db, wd = db_and_data
    load(db, wd)
    load(db, wd)
    assert int(db.query("SELECT COUNT(*) c FROM morador").iloc[0]["c"]) == 3
