-- Unified person-grain table for housing_reality (Census 2010 + PNADC).
-- One row per morador, with the household attributes flattened in (matches PNADC's shape).
-- Categorical fields hold normalized values (via Python enums at ETL time), not native codes.
-- Everything nullable except the meta backbone, so a source missing a field never breaks the insert.
CREATE TABLE IF NOT EXISTS morador (
    -- meta / chave
    provedor                   VARCHAR   NOT NULL,  -- instituição de origem: 'IBGE'
    fonte                      VARCHAR   NOT NULL,  -- dataset: 'census_2010' | 'pnadc_2025'
    ano                        INTEGER   NOT NULL,
    uf                         VARCHAR   NOT NULL,
    peso                       DOUBLE    NOT NULL,
    situacao                   VARCHAR,             -- urbana | rural
    id_domicilio               VARCHAR,             -- Censo: uf+area+controle. PNADC: pendente mapear UPA+dom

    -- domicílio
    especie_unidade_domestica  VARCHAR,
    condicao_ocupacao          VARCHAR,
    valor_aluguel              DOUBLE,
    material_paredes           VARCHAR,
    n_comodos                  INTEGER,
    n_dormitorios              INTEGER,
    n_moradores                INTEGER,
    agua                       VARCHAR,
    esgoto                     VARCHAR,
    lixo                       VARCHAR,
    energia                    VARCHAR,
    n_banheiros                INTEGER,
    geladeira                  BOOLEAN,
    maquina_lavar              BOOLEAN,
    celular                    BOOLEAN,
    auto_moto                  BOOLEAN,
    internet                   BOOLEAN,
    rendimento_domiciliar      DOUBLE,
    rendimento_per_capita      DOUBLE,

    -- pessoa
    sexo                       VARCHAR,
    idade                      INTEGER,
    cor_raca                   VARCHAR,
    relacao_responsavel        VARCHAR,
    nivel_instrucao            VARCHAR,

    -- só de uma fonte (nullable na outra)
    municipio                  INTEGER,             -- só Censo
    material_cobertura         VARCHAR,             -- só PNADC
    material_piso              VARCHAR,             -- só PNADC
    combustivel_cozinha        VARCHAR              -- só PNADC
);
