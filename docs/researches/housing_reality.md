# Realidade Habitacional

Pesquisa que mapeia as condições habitacionais brasileiras a partir dos microdados da amostra do Censo Demográfico 2010, publicados pelo IBGE. Serve como fundação empírica para um projeto de documentação de smart house.

## Fonte de dados

**IBGE — Censo Demográfico 2010, Microdados da Amostra**

- Instituição: Instituto Brasileiro de Geografia e Estatística (IBGE)
- Edição: Censo Demográfico 2010
- Tipo: Microdados da amostra (~27% dos domicílios)
- FTP: `https://ftp.ibge.gov.br/Censos/Censo_Demografico_2010/Resultados_Gerais_da_Amostra/Microdados/`
- Formato original: arquivo texto de largura fixa (FWF) compactado em ZIP, um por UF
- Documentação oficial: [Layout dos microdados](https://ftp.ibge.gov.br/Censos/Censo_Demografico_2010/Resultados_Gerais_da_Amostra/Microdados/Layout_Microdados_Amostra.ods)

## Arquivos coletados

Um ZIP por UF é baixado do FTP. Dentro de cada ZIP há quatro arquivos TXT:

| Arquivo interno | Chave interna | Descrição |
|---|---|---|
| `Amostra_Domicilios_<UF>.txt` | `domicilios` | Características físicas e de infraestrutura dos domicílios |
| `Amostra_Pessoas_<UF>.txt` | `pessoas` | Características sociodemográficas de cada morador |
| `Amostra_Emigracao_<UF>.txt` | `emigracao` | Pessoas do domicílio residindo no exterior em 31/07/2010 |
| `Amostra_Mortalidade_<UF>.txt` | `mortalidade` | Óbitos ocorridos no domicílio entre ago/2009 e jul/2010 |

Emigração e mortalidade são coletados e processados mas estão fora do escopo de análise inicial. Filtrar na consulta é responsabilidade da camada de análise.

## Pipeline de processamento

```
download()           → <UF>.zip  (idempotente — skip se já existe)
parse()              → parsed/<arquivo>.parquet
map_variables()      → mapped/<arquivo>.parquet
```

### parse()

1. Extrai o ZIP para `data/census_2010/<UF>/`
2. Lê cada TXT com `pandas.read_fwf` usando os layouts em `sources/census_2010_layout/*.csv`
3. Aplica dtypes otimizados (`Int8`, `Int16`, `Int32`, `Int64`, `Float64`)
4. Aplica escalonamento decimal nos campos com casas decimais implícitas (ex.: `V0010 / 10¹³`)
5. Salva em `data/census_2010/<UF>/parsed/<arquivo>.parquet` (Snappy)

### map_variables()

1. Lê o parquet de `parsed/`
2. Renomeia colunas de código IBGE para snake_case legível em português
   - Ex.: `V1006` → `situacao_do_domicilio`
   - Fallback: código lowercased se a descrição estiver vazia
3. Salva em `data/census_2010/<UF>/mapped/<arquivo>.parquet` (Snappy)

Ambas as etapas são idempotentes — se o parquet de destino já existir o passo é ignorado.

---

## Variáveis por arquivo

As tabelas abaixo descrevem as variáveis presentes nos parquets finais (`mapped/`). O nome da coluna é o snake_case derivado da descrição oficial do IBGE. Flags de imputação (prefixo `m_`) indicam se o valor foi imputado pelo IBGE.

### Variáveis comuns a todos os arquivos

| Coluna | Código IBGE | Descrição |
|---|---|---|
| `unidade_da_federacao` | V0001 | UF (código numérico IBGE) |
| `codigo_do_municipio` | V0002 | Código do município (IBGE) |
| `area_de_ponderacao` | V0011 | Área de ponderação |
| `controle` | V0300 | Número de controle do domicílio |
| `peso_amostral` | V0010 | Peso amostral (fator de expansão, dividido por 10¹³) |
| `regiao_geografica` | V1001 | Região geográfica (1–5) |
| `codigo_da_mesorregiao` | V1002 | Mesorregião |
| `codigo_da_microrregiao` | V1003 | Microrregião |
| `codigo_da_regiao_metropolitana` | V1004 | Região metropolitana |
| `situacao_do_domicilio` | V1006 | Situação: 1=Urbana, 2=Rural |
| `situacao_do_setor` | V1005 | Situação do setor censitário (1–8) |

---

### domicilios — 76 variáveis

Características físicas, de infraestrutura e econômicas do domicílio.

#### Identificação e estrutura

| Coluna | Código | Descrição |
|---|---|---|
| `especie_de_unidade_visitada` | V4001 | Tipo de unidade (dom. particular, coletivo, etc.) |
| `tipo_de_especie` | V4002 | Subtipo (casa, apartamento, cômodo, tenda, etc.) |

#### Condições de moradia

| Coluna | Código | Descrição |
|---|---|---|
| `domicilio_condicao_de_ocupacao` | V0201 | Próprio pago, próprio pagando, alugado, cedido, outra |
| `valor_do_aluguel_em_reais` | V2011 | Valor do aluguel (R$) |
| `aluguel_em_n_de_salarios_minimos` | V2012 | Aluguel em salários mínimos |
| `material_predominante_paredes_externas` | V0202 | Material das paredes (alvenaria, madeira, taipa, palha…) |
| `comodos_numero` | V0203 | Número de cômodos |
| `densidade_de_morador_comodo` | V6203 | Moradores por cômodo |
| `comodos_como_dormitorio_numero` | V0204 | Número de dormitórios |
| `densidade_de_morador_dormitorio` | V6204 | Moradores por dormitório |
| `adequacao_da_moradia` | V6210 | Adequação da moradia (1–3) |

#### Saneamento e serviços

| Coluna | Código | Descrição |
|---|---|---|
| `banheiros_de_uso_exclusivo_numero` | V0205 | Número de banheiros |
| `sanitario_ou_buraco_para_dejecoes_existencia` | V0206 | Tem sanitário |
| `esgotamento_sanitario_tipo` | V0207 | Tipo de esgotamento (rede geral, fossa, vala, rio…) |
| `abastecimento_de_agua_forma` | V0208 | Fonte de água (rede, poço, cisterna, carro-pipa…) |
| `abastecimento_de_agua_canalizacao` | V0209 | Canalização da água |
| `lixo_destino` | V0210 | Destinação do lixo |
| `energia_eletrica_existencia` | V0211 | Tem energia elétrica e origem |
| `existencia_de_medidor_ou_relogio_energia_eletrica_companhia_distribuidora` | V0212 | Medidor de energia |

#### Bens duráveis

| Coluna | Código | Descrição |
|---|---|---|
| `radio_existencia` | V0213 | Tem rádio |
| `televisao_existencia` | V0214 | Tem televisão |
| `maquina_de_lavar_roupa_existencia` | V0215 | Tem máquina de lavar |
| `geladeira_existencia` | V0216 | Tem geladeira |
| `telefone_celular_existencia` | V0217 | Tem celular |
| `telefone_fixo_existencia` | V0218 | Tem telefone fixo |
| `microcomputador_existencia` | V0219 | Tem microcomputador |
| `microcomputador_com_acesso_a_internet_existencia` | V0220 | Tem computador com internet |
| `motocicleta_para_uso_particular_existencia` | V0221 | Tem motocicleta |
| `automovel_para_uso_particular_existencia` | V0222 | Tem automóvel |

#### Composição e renda

| Coluna | Código | Descrição |
|---|---|---|
| `alguma_pessoa_que_morava_com_voces_estava_morando_em_outro_pais_em_31_de_julho_de_2010` | V0301 | Tem emigrante no exterior |
| `quantas_pessoas_moravam_neste_domicilio_em_31_de_julho_de_2010` | V0401 | Total de moradores |
| `a_responsabilidade_pelo_domicilio_e_de` | V0402 | Um ou mais responsáveis |
| `de_agosto_de_2009_a_julho_de_2010_faleceu_alguma_pessoa_que_morava_com_voces_inclusive_criancas_recem_nascidas_e_idosos` | V0701 | Óbito no domicílio no período |
| `rendimento_mensal_domiciliar_em_julho_de_2010` | V6529 | Rendimento domiciliar (R$) |
| `rendimento_domiciliar_salarios_minimos_em_julho_de_2010` | V6530 | Rendimento em salários mínimos |
| `rendimento_domiciliar_per_capita_em_julho_de_2010` | V6531 | Renda per capita (R$) |
| `rendimento_domiciliar_per_capita_em_n_de_salarios_minimos_em_julho_de_2010` | V6532 | Renda per capita em salários mínimos |
| `v6600` | V6600 | Espécie da unidade doméstica (unipessoal, nuclear, estendida, composta) |

#### Flags de imputação

22 variáveis com prefixo `m_` indicam se o campo correspondente foi imputado pelo IBGE (`1=Sim`, `2=Não`): `m_imputacao_na_v0201` … `m_imputacao_na_v0701`.

---

### pessoas — 244 variáveis

Características sociodemográficas de cada morador recenseado.

#### Identificação no domicílio

| Coluna | Código | Descrição |
|---|---|---|
| `relacao_de_parentesco_ou_de_convivencia_com_a_pessoa_responsavel_pelo_domicilio` | V0502 | Relação com o responsável (01=responsável, 02=cônjuge, 04=filho…) |
| `ordem_logica` | V0504 | Ordem lógica da pessoa no questionário |

#### Perfil demográfico

| Coluna | Código | Descrição |
|---|---|---|
| `sexo` | V0601 | 1=Masculino, 2=Feminino |
| `v6033` | V6033 | Idade calculada (anos e meses) |
| `v6036` | V6036 | Idade em anos |
| `v6037` | V6037 | Idade em meses (< 1 ano) |
| `forma_de_declaracao_da_idade` | V6040 | 1=Data de nascimento, 2=Idade declarada |
| `cor_ou_raca` | V0606 | 1=Branca, 2=Preta, 3=Amarela, 4=Parda, 5=Indígena |
| `registro_de_nascimento` | V0613 | Tipo de registro de nascimento |

#### Deficiências

| Coluna | Código | Descrição |
|---|---|---|
| `dificuldade_permanente_de_enxergar` | V0614 | Grau de dificuldade visual (1–4) |
| `dificuldade_permanente_de_ouvir` | V0615 | Grau de dificuldade auditiva (1–4) |
| `dificuldade_permanente_de_caminhar_ou_subir_degraus` | V0616 | Grau de dificuldade motora (1–4) |
| `deficiencia_mental_intelectual_permanente` | V0617 | Tem deficiência intelectual |

#### Migração e naturalidade

Inclui variáveis de município e UF de nascimento, UF de residência anterior, tempo de moradia, e país estrangeiro de origem (código IBGE). Ver layout completo em `sources/census_2010_layout/pessoas.csv`.

#### Educação

Inclui alfabetização, curso frequentado, série/ano, nível de instrução, anos de estudo, e frequência à creche/pré-escola.

#### Trabalho e rendimento

Inclui posição na ocupação, horas trabalhadas, ramos de atividade, rendimentos de todas as fontes (trabalho principal/secundário, aposentadoria, outros), e rendimento total.

> O arquivo `pessoas` é o mais extenso: 244 variáveis, ~26MB por UF em parquet.
> Para o dicionário completo consulte `sources/census_2010_layout/pessoas.csv`.

---

### emigracao — 19 variáveis

Um registro por pessoa do domicílio que estava morando no exterior em 31/07/2010.

| Coluna | Código | Descrição |
|---|---|---|
| `relacao_de_parentesco_ou_de_convivencia_com_a_pessoa_responsavel_pelo_domicilio` | V0502 | Relação com o responsável |
| `sexo_do_emigrante` | V0303 | 1=Masculino, 2=Feminino |
| `ano_de_nascimento_do_emigrante` | V0304 | Ano de nascimento |
| `ano_da_ultima_partida_do_emigrante` | V0305 | Ano da última partida do Brasil |
| `pais_de_residencia_em_31_de_julho_de_2010_codigo` | V3061 | País de residência (código IBGE) |

Flags de imputação: `m_imputacao_na_v0303`, `m_imputacao_na_v0304`, `m_imputacao_na_v0305`, `m_imputacao_na_v3061`.

---

### mortalidade — 19 variáveis

Um registro por óbito ocorrido no domicílio entre agosto/2009 e julho/2010.

| Coluna | Código | Descrição |
|---|---|---|
| `mes_e_ano_de_falecimento` | V0703 | Mês/ano do óbito (01=ago/2009 … 12=jul/2010) |
| `sexo_da_pessoa_falecida` | V0704 | 1=Masculino, 2=Feminino |
| `v7051` | V7051 | Idade ao falecer em anos |
| `v7052` | V7052 | Idade ao falecer em meses (< 1 ano) |

Flags de imputação: `m_imputacao_na_v0703`, `m_imputacao_na_v0704`, `m_imputacao_na_v7051`, `m_imputacao_na_v7052`.

---

## Formato de saída

| Atributo | Valor |
|---|---|
| Formato | Apache Parquet |
| Compressão | Snappy |
| Caminho local | `data/census_2010/<UF>/mapped/<arquivo>.parquet` |
| Dtypes numéricos | `Int8` / `Int16` / `Int32` / `Int64` / `Float64` (nullable) |
| Escalonamento | Aplicado em parse — valores já representam a grandeza real |

## Notas

- **Peso amostral**: `V0010` é armazenado com 13 casas decimais implícitas no FWF. O parse divide por 10¹³ para obter o fator de expansão real. Desvio validado contra IBGE SIDRA (AC): 2,8%.
- **Cobertura**: 27 UFs × 4 arquivos = 108 parquets por rodada completa.
- **Idempotência**: re-rodar o pipeline sobre UFs já processadas é seguro — qualquer arquivo existente é ignorado.
