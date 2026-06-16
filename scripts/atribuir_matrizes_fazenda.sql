-- =============================================================================
-- atribuir_matrizes_fazenda.sql
-- WiNS Hub Agro -- prospeccao
--
-- OBJETIVO
--   Distribuir o rebanho/matrizes estimadas por MUNICIPIO
--   (prospeccao.rebanho_municipio) entre as FAZENDAS de cada municipio,
--   por PARTICIPACAO DE AREA, calibrando para somar o total municipal.
--
--   Este e o passo DOWNSTREAM do geomatch: o geomatch (outras frentes)
--   produz, por lead/fazenda, um codigo_car + area_total_ha. Aqui assumimos
--   que essa area ja existe (tabela de entrada prospeccao.fazenda_area) e
--   construimos o motor de atribuicao pronto para plugar.
--
-- FORMULA (atribuicao bruta por participacao de area):
--
--     matrizes_estim_fazenda
--         = matrizes_municipio
--           * ( area_ha_fazenda / SUM(area_ha) das fazendas CONHECIDAS no municipio )
--
--   Idem para bovinos:
--     bovinos_estim_fazenda
--         = bovinos_municipio * (area_ha_fazenda / SUM(area_ha conhecida))
--
-- RESSALVA DE COBERTURA  (importante -- ler antes de usar em producao):
--   A formula acima NORMALIZA pela soma das areas CONHECIDAS, nao pela area
--   total de pasto do municipio. Logo, ela SEMPRE redistribui 100% do rebanho
--   municipal entre as poucas fazendas que conhecemos -> SUPERATRIBUI quando a
--   cobertura e baixa (ex.: conhecemos 3 fazendas que somam 5% do pasto, mas a
--   formula joga 100% das matrizes nessas 3).
--
--   Por isso a query reporta uma "cobertura" e oferece DOIS modos:
--     (A) modo_participacao  -> normaliza por SUM(area_conhecida)  [bruto]
--     (B) modo_calibrado     -> usa a fracao area_conhecida/pasto_municipal
--                               como teto; so deve ser confiado quando a
--                               cobertura e alta (ex.: > 0.7). Quando ha
--                               pasto_municipal_ha, a matriz por fazenda vira:
--                                 matrizes_municipio
--                                   * (area_ha_fazenda / pasto_municipal_ha)
--                               (densidade municipal real * area da fazenda),
--                               que NAO superatribui mas SUBESTIMA se a fazenda
--                               for mais intensiva que a media municipal.
--
--   Recomendacao operacional: usar (A) so para ranquear/priorizar leads dentro
--   do mesmo municipio (a ordem relativa e robusta); usar o valor ABSOLUTO de
--   matrizes apenas quando cobertura_area >= ~0.7, e sinalizar
--   `confiavel_absoluto` = false caso contrario.
--
-- SEGURANCA / LGPD:
--   fazenda_area guarda apenas cnpj_basico (PJ) ou um hash de chave do geomatch.
--   NUNCA gravar CPF de pessoa fisica vindo de CAR/INCRA aqui (ver
--   deliverables/MEMO_LGPD_geomatch.md). area_ha e dado agregado/derivado, ok.
--
-- USO:
--   docker exec -i wins_agro_v1-db-1 psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
--     -f /caminho/atribuir_matrizes_fazenda.sql
--   (o bloco de DEMO sintetica esta delimitado e e auto-limpante.)
-- =============================================================================

SET search_path TO prospeccao, public;

-- -----------------------------------------------------------------------------
-- 1) TABELA DE ENTRADA -- preenchida pelo geomatch (qualquer frente)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prospeccao.fazenda_area (
    fazenda_area_id  bigserial PRIMARY KEY,
    -- chave do lead PJ; NULL quando o lead so tem chave de geomatch (ver lead_ref).
    cnpj_basico      char(8),
    -- codigo CAR da fazenda (geomatch CAR/SICAR). Identifica o imovel, nao a pessoa.
    codigo_car       varchar(50),
    -- municipio IBGE do imovel (chave de juncao com rebanho_municipio).
    codigo_ibge      integer NOT NULL,
    -- area da fazenda em hectares (capacidade). Vem do geomatch / CAR / SIGEF.
    area_ha          numeric(12,2) NOT NULL CHECK (area_ha > 0),
    -- referencia opaca do lead quando nao ha CNPJ (ex.: id interno, hash).
    -- NUNCA armazenar CPF de pessoa fisica aqui.
    lead_ref         varchar(80),
    fonte_geomatch   varchar(40),          -- 'CAR_SP','SIGEF','RFB_GEOCODE',...
    updated_at       timestamptz DEFAULT now()
);

COMMENT ON TABLE prospeccao.fazenda_area IS
  'INPUT do motor de atribuicao de matrizes por fazenda. Preenchida pelo GEOMATCH '
  '(outras frentes): cada linha = uma fazenda com area_ha e seu codigo_ibge. '
  'NUNCA gravar CPF de pessoa fisica (ver deliverables/MEMO_LGPD_geomatch.md). '
  'Pode estar vazia: o motor (v_fazenda_matriz) so produz linhas onde ha area.';
COMMENT ON COLUMN prospeccao.fazenda_area.cnpj_basico IS 'CNPJ basico (8 dig) do lead PJ; NULL se geomatch nao resolveu PJ.';
COMMENT ON COLUMN prospeccao.fazenda_area.codigo_car IS 'Codigo CAR do imovel (identifica fazenda, nao pessoa).';
COMMENT ON COLUMN prospeccao.fazenda_area.area_ha    IS 'Area total/capacidade da fazenda em ha, fornecida pelo geomatch.';
COMMENT ON COLUMN prospeccao.fazenda_area.lead_ref   IS 'Ref opaca do lead quando nao ha CNPJ. NUNCA CPF de PF.';

CREATE INDEX IF NOT EXISTS idx_fazenda_area_ibge ON prospeccao.fazenda_area (codigo_ibge);

-- -----------------------------------------------------------------------------
-- 1b) (OPCIONAL) pasto municipal para o modo CALIBRADO.
--     Coluna de teto: area total de pastagem do municipio (ex.: MapBiomas).
--     Se ausente, o modo calibrado simplesmente nao se aplica e caimos no
--     modo participacao. Mantida como tabela leve, opcional.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prospeccao.pasto_municipal (
    codigo_ibge        integer PRIMARY KEY,
    pasto_municipal_ha numeric(14,2) CHECK (pasto_municipal_ha > 0),
    fonte              varchar(60) DEFAULT 'MapBiomas (agregado municipal)'
);
COMMENT ON TABLE prospeccao.pasto_municipal IS
  'OPCIONAL. Area de pastagem por municipio, teto para o modo CALIBRADO da '
  'atribuicao de matrizes. Preenchida via agregacao MapBiomas. Pode ficar vazia.';

-- -----------------------------------------------------------------------------
-- 2) MOTOR DE ATRIBUICAO -- view (recalcula sempre que fazenda_area muda)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW prospeccao.v_fazenda_matriz AS
WITH muni AS (
    SELECT codigo_ibge,
           SUM(area_ha)        AS area_conhecida_ha,
           COUNT(*)            AS n_fazendas_conhecidas
    FROM prospeccao.fazenda_area
    GROUP BY codigo_ibge
)
SELECT
    fa.fazenda_area_id,
    fa.cnpj_basico,
    fa.codigo_car,
    fa.lead_ref,
    fa.fonte_geomatch,
    fa.codigo_ibge,
    rm.municipio,
    rm.uf,
    fa.area_ha,
    m.area_conhecida_ha,
    m.n_fazendas_conhecidas,
    rm.bovinos_ppm2024     AS bovinos_municipio,
    rm.matrizes_estim2024  AS matrizes_municipio,

    -- participacao de area da fazenda (sobre o conhecido)
    ROUND(fa.area_ha / m.area_conhecida_ha, 6)               AS share_area,

    -- (A) MODO PARTICIPACAO -- bruto, soma 100% do municipio entre conhecidas
    ROUND(rm.matrizes_estim2024 * fa.area_ha / m.area_conhecida_ha)::bigint
                                                             AS matrizes_estim_fazenda,
    ROUND(rm.bovinos_ppm2024 * fa.area_ha / m.area_conhecida_ha)::bigint
                                                             AS bovinos_estim_fazenda,

    -- (B) MODO CALIBRADO -- densidade municipal real x area da fazenda.
    --     So existe quando ha pasto_municipal_ha. Nao superatribui.
    CASE WHEN pm.pasto_municipal_ha IS NOT NULL THEN
        ROUND(rm.matrizes_estim2024 * fa.area_ha / pm.pasto_municipal_ha)::bigint
    END                                                      AS matrizes_estim_fazenda_calibrado,

    -- cobertura de area: quanto do pasto municipal as fazendas conhecidas cobrem.
    -- NULL quando nao temos pasto_municipal_ha.
    CASE WHEN pm.pasto_municipal_ha IS NOT NULL THEN
        ROUND(m.area_conhecida_ha / pm.pasto_municipal_ha, 4)
    END                                                      AS cobertura_area,

    -- flag pratica: so confie no VALOR ABSOLUTO de matrizes quando a cobertura
    -- e alta; caso contrario o modo participacao superatribui. Sem pasto
    -- municipal nao da pra afirmar -> false (use so para ranquear).
    CASE
        WHEN pm.pasto_municipal_ha IS NULL THEN false
        WHEN m.area_conhecida_ha / pm.pasto_municipal_ha >= 0.70 THEN true
        ELSE false
    END                                                      AS confiavel_absoluto
FROM prospeccao.fazenda_area fa
JOIN muni m                       ON m.codigo_ibge  = fa.codigo_ibge
JOIN prospeccao.rebanho_municipio rm ON rm.codigo_ibge = fa.codigo_ibge
LEFT JOIN prospeccao.pasto_municipal pm ON pm.codigo_ibge = fa.codigo_ibge;

COMMENT ON VIEW prospeccao.v_fazenda_matriz IS
  'Atribuicao de matrizes/bovinos por fazenda a partir de fazenda_area (geomatch) '
  'x rebanho_municipio. matrizes_estim_fazenda = modo PARTICIPACAO (bruto). '
  'matrizes_estim_fazenda_calibrado + confiavel_absoluto so quando ha '
  'pasto_municipal. Sanity: SUM(matrizes_estim_fazenda) por municipio = '
  'matrizes_municipio (auto-calibra).';

-- =============================================================================
-- DEMO SINTETICA  (BEGIN ... ROLLBACK -> nao deixa lixo no banco)
-- =============================================================================
BEGIN;

-- Dois municipios reais de alta matriz:
--   1507300 = Sao Felix do Xingu/PA  (matrizes_estim2024 = 967.646)
--   5003207 = Corumba/MS             (matrizes_estim2024 = 946.201)
INSERT INTO prospeccao.fazenda_area (cnpj_basico, codigo_car, codigo_ibge, area_ha, lead_ref, fonte_geomatch) VALUES
  ('11111111','PA-1507300-AAA', 1507300, 12000.00, 'demo-faz-A', 'DEMO'),
  ('22222222','PA-1507300-BBB', 1507300,  6000.00, 'demo-faz-B', 'DEMO'),
  (NULL,       'PA-1507300-CCC', 1507300,  2000.00, 'demo-faz-C', 'DEMO'),
  ('33333333','MS-5003207-AAA', 5003207, 40000.00, 'demo-faz-D', 'DEMO'),
  ('44444444','MS-5003207-BBB', 5003207, 25000.00, 'demo-faz-E', 'DEMO'),
  (NULL,       'MS-5003207-CCC', 5003207, 15000.00, 'demo-faz-F', 'DEMO');

-- Pasto municipal sintetico para exercitar o modo CALIBRADO:
--   Sao Felix: cobertura ALTA  (conhecido 20.000 / 25.000 = 0,80 -> confiavel)
--   Corumba  : cobertura BAIXA (conhecido 80.000 / 1.000.000 = 0,08 -> NAO confiavel)
INSERT INTO prospeccao.pasto_municipal (codigo_ibge, pasto_municipal_ha, fonte) VALUES
  (1507300,    25000.00, 'DEMO'),
  (5003207, 1000000.00, 'DEMO');

\echo '=== DEMO: atribuicao por fazenda ==='
SELECT codigo_ibge, municipio, uf, codigo_car, area_ha,
       share_area, matrizes_municipio, matrizes_estim_fazenda,
       matrizes_estim_fazenda_calibrado AS matriz_calibrado,
       cobertura_area, confiavel_absoluto
FROM prospeccao.v_fazenda_matriz
ORDER BY codigo_ibge, matrizes_estim_fazenda DESC;

\echo '=== SANITY: soma das fazendas conhecidas (modo participacao) == matriz do municipio ==='
SELECT codigo_ibge,
       MAX(matrizes_municipio)            AS matriz_municipio,
       SUM(matrizes_estim_fazenda)        AS soma_atribuida_participacao,
       SUM(matrizes_estim_fazenda_calibrado) AS soma_atribuida_calibrado
FROM prospeccao.v_fazenda_matriz
GROUP BY codigo_ibge
ORDER BY codigo_ibge;

-- LIMPEZA: rollback descarta TODOS os dados sinteticos (fazenda_area + pasto).
ROLLBACK;

\echo '=== POS-LIMPEZA: fazenda_area e pasto_municipal devem estar vazias ==='
SELECT 'fazenda_area'    AS tabela, COUNT(*) AS linhas FROM prospeccao.fazenda_area
UNION ALL
SELECT 'pasto_municipal' AS tabela, COUNT(*) AS linhas FROM prospeccao.pasto_municipal;
