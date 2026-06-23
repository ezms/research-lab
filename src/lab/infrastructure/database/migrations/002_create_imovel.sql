-- Inventory of physical property spaces (E2 — property_inventory slice).
-- One row per listing. All fields nullable except meta backbone.
-- Boolean amenity columns cover the full range: kitnet (mostly NULL) to chácara (mostly populated).
-- descricao_texto captures structural ambiguities (sala→quarto, etc.) for notebook analysis.
CREATE TABLE IF NOT EXISTS imovel (
    -- meta
    provedor            VARCHAR   NOT NULL,
    url                 VARCHAR,
    id_externo          VARCHAR,
    data_coleta         TIMESTAMP DEFAULT now(),
    negocio             VARCHAR,             -- aluguel | venda | temporada

    -- localização
    uf                  VARCHAR,
    cidade              VARCHAR,
    bairro              VARCHAR,
    cep                 VARCHAR,

    -- tipo
    tipo_imovel         VARCHAR,

    -- áreas
    area_total_m2       DOUBLE,
    area_construida_m2  DOUBLE,
    area_terreno_m2     DOUBLE,

    -- estrutura / cômodos
    n_andares           INTEGER,
    andar               INTEGER,             -- qual andar (apartamentos)
    n_quartos           INTEGER,
    n_suites            INTEGER,
    n_banheiros         INTEGER,
    n_lavabos           INTEGER,
    n_salas             INTEGER,
    n_cozinhas          INTEGER,
    n_areas_servico     INTEGER,

    -- circulação vertical
    tem_escada          BOOLEAN,
    tem_elevador        BOOLEAN,
    tem_rampa           BOOLEAN,

    -- garagem
    tem_garagem         BOOLEAN,
    n_garagens          INTEGER,
    n_vagas_total       INTEGER,
    tipo_garagem        VARCHAR,             -- coberta | descoberta | subsolo | misto

    -- espaços internos extras
    tem_sotao           BOOLEAN,
    tem_porao           BOOLEAN,
    tem_adega           BOOLEAN,
    tem_despensa        BOOLEAN,
    tem_escritorio      BOOLEAN,
    tem_quarto_servico  BOOLEAN,
    tem_home_theater    BOOLEAN,

    -- áreas externas
    tem_jardim          BOOLEAN,
    tem_quintal         BOOLEAN,
    tem_varanda         BOOLEAN,
    tem_sacada          BOOLEAN,
    tem_terraco         BOOLEAN,
    tem_area_gourmet    BOOLEAN,
    tem_churrasqueira   BOOLEAN,
    tem_piscina         BOOLEAN,
    tem_edicola         BOOLEAN,
    tem_area_pet        BOOLEAN,

    -- lazer / esporte
    tipos_quadra        VARCHAR,             -- ex: 'tenis, basquete, poliesportiva'
    tem_academia        BOOLEAN,
    tem_playground      BOOLEAN,
    tem_sauna           BOOLEAN,
    tem_spa             BOOLEAN,

    -- espaços coletivos (condomínio)
    tem_salao_festas    BOOLEAN,
    tem_salao_jogos     BOOLEAN,
    tem_portaria        BOOLEAN,

    -- rural
    tem_pomar           BOOLEAN,
    tem_horta           BOOLEAN,
    tem_lago            BOOLEAN,
    tem_sistema_irrigacao BOOLEAN,

    -- segurança
    tem_muro            BOOLEAN,
    tem_portao          BOOLEAN,
    tem_portao_eletrico BOOLEAN,
    tem_interfone       BOOLEAN,
    tem_camera          BOOLEAN,
    tem_alarme          BOOLEAN,
    tem_cerca_eletrica  BOOLEAN,

    -- infraestrutura
    tem_ar_condicionado   BOOLEAN,
    tem_aquecimento_solar BOOLEAN,
    tem_placa_solar       BOOLEAN,
    tem_gerador           BOOLEAN,
    tem_nobreak           BOOLEAN,
    tem_poco_artesiano    BOOLEAN,
    tem_cisterna          BOOLEAN,

    -- valor
    valor_aluguel       DOUBLE,
    valor_venda         DOUBLE,
    valor_condominio    DOUBLE,
    valor_iptu          DOUBLE,

    -- texto livre (ambiguidades arquitetônicas para análise posterior)
    titulo_anuncio      VARCHAR,
    descricao_texto     VARCHAR
);
