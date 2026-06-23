"""ETL: parquets coletados -> tabela unificada `morador` (grão de pessoa).

Idempotente: re-inserir uma fonte apaga as linhas dela antes.
"""
import logging
import os
from pathlib import Path

from lab.infrastructure.database.duckdb_adapter import DuckDBAdapter

_log = logging.getLogger(__name__)

# -- códigos universais IBGE (mesmo em Censo e PNADC) --
_SITUACAO = "CASE {c} WHEN 1 THEN 'urbana' WHEN 2 THEN 'rural' END"
_SEXO     = "CASE {c} WHEN 1 THEN 'masculino' WHEN 2 THEN 'feminino' END"
_COR      = (
    "CASE {c} WHEN 1 THEN 'branca' WHEN 2 THEN 'preta' WHEN 3 THEN 'amarela'"
    " WHEN 4 THEN 'parda' WHEN 5 THEN 'indigena' WHEN 9 THEN 'ignorada' END"
)

# -- abastecimento de água (codificações distintas por fonte) --
_AGUA_CENSUS = (
    "CASE {c} WHEN 1 THEN 'rede_geral'"
    " WHEN 2 THEN 'poco_nascente' WHEN 3 THEN 'poco_nascente'"
    " WHEN 9 THEN 'poco_nascente' WHEN 10 THEN 'poco_nascente'"
    " WHEN 4 THEN 'carro_pipa'"
    " WHEN 5 THEN 'chuva' WHEN 6 THEN 'chuva'"
    " WHEN 7 THEN 'rio_lago'"
    " ELSE 'outro' END"
)
_AGUA_PNADC = (
    "CASE {c} WHEN 1 THEN 'rede_geral'"
    " WHEN 2 THEN 'poco_artesiano' WHEN 3 THEN 'poco_raso'"
    " WHEN 4 THEN 'fonte_nascente' WHEN 5 THEN 'chuva'"
    " ELSE 'outro' END"
)

# -- esgoto (codificações distintas por fonte) --
_ESGOTO_CENSUS = (
    "CASE {c} WHEN 1 THEN 'rede_geral'"
    " WHEN 2 THEN 'fossa_septica' WHEN 3 THEN 'fossa_rudimentar'"
    " WHEN 4 THEN 'vala' WHEN 5 THEN 'rio_lago_mar'"
    " ELSE 'outro' END"
)
_ESGOTO_PNADC = (
    "CASE {c} WHEN 1 THEN 'rede_geral'"
    " WHEN 2 THEN 'fossa_septica_ligada' WHEN 3 THEN 'fossa_septica_nao_ligada'"
    " WHEN 4 THEN 'fossa_rudimentar' WHEN 5 THEN 'vala'"
    " WHEN 6 THEN 'rio_lago_mar'"
    " ELSE 'outro' END"
)

# -- energia: normalizada como 'sim'/'nao' entre fontes --
_ENERGIA_CENSUS = "CASE {c} WHEN 1 THEN 'sim' WHEN 2 THEN 'sim' WHEN 3 THEN 'nao' END"
_ENERGIA_PNADC  = "CASE {c} WHEN 1 THEN 'sim' WHEN 2 THEN 'nao' END"

# -- combustível cozinha (só PNADC) --
_COMBUSTIVEL = (
    "CASE {c} WHEN 1 THEN 'gas_botijao' WHEN 2 THEN 'gas_encanado'"
    " WHEN 3 THEN 'lenha_carvao' WHEN 4 THEN 'energia_eletrica'"
    " WHEN 5 THEN 'outro' END"
)

_COLS = (
    "provedor, fonte, ano, uf, peso, situacao, id_domicilio, "
    "n_comodos, n_dormitorios, n_moradores, n_banheiros, valor_aluguel, "
    "rendimento_domiciliar, rendimento_per_capita, "
    "agua, esgoto, energia, geladeira, maquina_lavar, internet, auto_moto, "
    "municipio, sexo, idade, cor_raca, combustivel_cozinha"
)


def _work_dir() -> Path:
    return Path(os.environ.get("RESEARCH_LAB_DATA_DIR", "data"))


def _load_census(db: DuckDBAdapter, work_dir: Path) -> None:
    base = work_dir / "census_2010"
    for uf_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        dom = uf_dir / "mapped" / "domicilios.parquet"
        pes = uf_dir / "mapped" / "pessoas.parquet"
        if not (dom.exists() and pes.exists()):
            continue
        uf = uf_dir.name
        db.execute(f"""
            INSERT INTO morador ({_COLS})
            SELECT
                'IBGE', 'census_2010', 2010, '{uf}', p.peso_amostral,
                {_SITUACAO.format(c='d.situacao_do_domicilio')},
                '{uf}_' || d.area_de_ponderacao || '_' || d.controle,
                d.comodos_numero,
                d.comodos_como_dormitorio_numero,
                d.quantas_pessoas_moravam_neste_domicilio_em_31_de_julho_de_2010,
                d.banheiros_de_uso_exclusivo_numero,
                d.valor_do_aluguel_em_reais,
                d.rendimento_mensal_domiciliar_em_julho_de_2010,
                d.rendimento_domiciliar_per_capita_em_julho_de_2010,
                {_AGUA_CENSUS.format(c='d.abastecimento_de_agua_forma')},
                {_ESGOTO_CENSUS.format(c='d.esgotamento_sanitario_tipo')},
                {_ENERGIA_CENSUS.format(c='d.energia_eletrica_existencia')},
                d.geladeira_existencia = 1,
                d.maquina_de_lavar_roupa_existencia = 1,
                d.microcomputador_com_acesso_a_internet_existencia = 1,
                (d.automovel_para_uso_particular_existencia = 1
                 OR d.motocicleta_para_uso_particular_existencia = 1),
                d.codigo_do_municipio,
                {_SEXO.format(c='p.sexo')},
                p.variavel_auxiliar_da_idade_calculada_em_anos,
                {_COR.format(c='p.cor_ou_raca')},
                NULL
            FROM read_parquet('{pes}') p
            JOIN read_parquet('{dom}') d
              ON p.area_de_ponderacao = d.area_de_ponderacao
             AND p.controle = d.controle
        """)


def _load_pnadc(db: DuckDBAdapter, work_dir: Path, year: int = 2025) -> None:
    glob = str(work_dir / "pnadc" / str(year) / "mapped" / "*.parquet")
    db.execute(f"""
        INSERT INTO morador ({_COLS})
        SELECT
            'IBGE', 'pnadc_{year}', {year}, uf, peso_com_calibracao,
            {_SITUACAO.format(c='tipo_de_situacao_da_regiao')},
            CAST(upa AS VARCHAR) || '_'
                || CAST(numero_de_selecao_do_domicilio AS VARCHAR)
                || '_' || CAST(painel AS VARCHAR),
            numero_de_comodos,
            numero_de_dormitorios,
            numero_de_pessoas_no_domicilio,
            numero_de_banheiros_exclusivos_dos_moradores,
            valor_do_aluguel_mensal,
            rendimento_habitual_domiciliar_mensal,
            rendimento_habitual_domiciliar_per_capita_mensal,
            {_AGUA_PNADC.format(c='principal_forma_de_abastecimento_de_agua')},
            {_ESGOTO_PNADC.format(c='destino_do_esgoto_do_banheiro')},
            {_ENERGIA_PNADC.format(c='origem_da_energia_eletrica')},
            domicilio_possui_geladeira IN (1, 2),
            domicilio_possui_maquina_de_lavar_roupa = 1,
            acessa_a_internet = 1,
            possui_automovel_ou_motocicleta_de_uso_pessoal = 1,
            NULL,
            {_SEXO.format(c='sexo')},
            idade_na_data_de_referencia,
            {_COR.format(c='cor_ou_raca')},
            {_COMBUSTIVEL.format(c='combustivel_mais_utilizado_na_preparacao_dos_alimentos')}
        FROM read_parquet('{glob}')
    """)


def load(db: DuckDBAdapter, work_dir: Path | None = None) -> dict[str, int]:
    """Popula `morador` com Censo 2010 + PNADC 2025. Retorna contagem por fonte."""
    work_dir = work_dir or _work_dir()
    for fonte in ("census_2010", "pnadc_2025"):
        db.execute(f"DELETE FROM morador WHERE fonte = '{fonte}'")
    _load_census(db, work_dir)
    _load_pnadc(db, work_dir)
    rows = db.query("SELECT fonte, COUNT(*) AS n FROM morador GROUP BY fonte")
    counts = dict(zip(rows["fonte"], rows["n"]))
    _log.info("morador carregada: %s", counts)
    return counts


if __name__ == "__main__":
    from dotenv import load_dotenv

    from lab.infrastructure.database.migrations import apply_migrations
    from lab.infrastructure.research.duckdb_repository import make_db

    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    _db = make_db()
    apply_migrations(_db)
    print("morador carregada:", load(_db))
