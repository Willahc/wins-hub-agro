-- =====================================================================
-- prospeccao.territorio_oportunidade
-- Mapa de território x oportunidade por município (1 linha / codigo_ibge).
-- Backbone: prospeccao.rebanho_municipio (5.571 municípios).
--
-- SCORE (0-1) = soma ponderada de 3 eixos normalizados por cume_dist
--   (rank percentil 0-1, robusto a outliers) sobre log1p do valor bruto:
--
--   demanda      (peso 0.45): matrizes_estim2024  -> n_demanda
--                 (mercado de reprodução = nosso TAM real)
--   compra ativa (peso 0.35): SICOR investimento. Combina:
--                 - crédito matrizes/reprodutores (cd_produto 7580) com
--                   PESO 0.65 (sinal mais afiado de compra de genética)
--                 - crédito bovinos geral      (cd_produto 1300) PESO 0.35
--                 -> n_sicor  (cume_dist do log1p do blend)
--   deserto vet  (peso 0.20): 1.0 se deserto_vet senao 0.0
--                 (sem assistência técnica local = porta aberta p/ canal)
--
--   score_oportunidade = 0.45*n_demanda + 0.35*n_sicor + 0.20*deserto_vet
--
-- gap_canal = TRUE quando score_oportunidade >= 0.70 (alta oportunidade)
--   E canal nosso fraco: (n_tecnicos_nossos = 0) E
--   (n_leads_nossos baixo p/ a demanda -> < percentil 40 de leads).
--   = município com muita matriz/demanda e SEM nosso canal = alvo de garimpo.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS unaccent;

DROP MATERIALIZED VIEW IF EXISTS prospeccao.territorio_oportunidade;

CREATE MATERIALIZED VIEW prospeccao.territorio_oportunidade AS
WITH base AS (
    SELECT r.codigo_ibge, r.municipio, r.uf,
           r.matrizes_estim2024, r.bovinos_ppm2024
    FROM prospeccao.rebanho_municipio r
),
-- SICOR investimento bovinos (1300) somado 2021-2025
sic_bov AS (
    SELECT codigo_ibge,
           sum(vl_total_brl)::numeric AS vl_bov,
           sum(n_contratos)::int       AS n_bov
    FROM prospeccao.sicor_credito_municipio
    WHERE finalidade='INVESTIMENTO' AND cd_produto='1300'
      AND ano BETWEEN 2021 AND 2025 AND codigo_ibge IS NOT NULL
    GROUP BY codigo_ibge
),
-- SICOR matrizes e reprodutores (7580) somado 2021-2025 (sinal afiado)
sic_mat AS (
    SELECT codigo_ibge,
           sum(vl_total_brl)::numeric AS vl_mat,
           sum(n_contratos)::int       AS n_mat
    FROM prospeccao.sicor_credito_municipio
    WHERE finalidade='INVESTIMENTO' AND cd_produto='7580'
      AND ano BETWEEN 2021 AND 2025 AND codigo_ibge IS NOT NULL
    GROUP BY codigo_ibge
),
-- Censo IA
ia AS (
    SELECT codigo_ibge, estab_sem_ia, estab_bovinos
    FROM prospeccao.censo2017_ia_municipio
),
-- Leads nossos por município (normaliza nome -> codigo_ibge via referencia)
fn_norm AS (
    SELECT m.codigo_ibge, count(*) AS n_leads
    FROM prospeccao.fazenda_nacional f
    JOIN referencia.municipio m
      ON m.nome_normalizado = upper(unaccent(f.municipio))
     AND m.uf = f.uf
    WHERE f.municipio IS NOT NULL
    GROUP BY m.codigo_ibge
),
-- Técnicos nossos (canal_tecnico + tecnico_zap) mapeados a município
-- via cnpj_basico -> fazenda_nacional.municipio -> referencia.municipio.
tec_cnpj AS (
    SELECT cnpj_basico FROM prospeccao.canal_tecnico
    UNION
    SELECT substring(cnpj14 FROM 1 FOR 8) FROM prospeccao.tecnico_zap
),
tec_mun AS (
    SELECT m.codigo_ibge, count(DISTINCT f.cnpj_basico) AS n_tecnicos
    FROM tec_cnpj t
    JOIN prospeccao.fazenda_nacional f ON f.cnpj_basico = t.cnpj_basico
    JOIN referencia.municipio m
      ON m.nome_normalizado = upper(unaccent(f.municipio))
     AND m.uf = f.uf
    WHERE f.municipio IS NOT NULL
    GROUP BY m.codigo_ibge
),
-- Vet supply / deserto
vet AS (
    SELECT codigo_ibge, n_vet FROM prospeccao.mv_vet_supply_mun
),
joined AS (
    SELECT b.codigo_ibge, b.municipio, b.uf,
           b.matrizes_estim2024, b.bovinos_ppm2024,
           COALESCE(sb.vl_bov,0)::numeric AS sicor_invest_bovinos_2125,
           COALESCE(sb.n_bov,0)           AS sicor_bovinos_contratos,
           COALESCE(sm.vl_mat,0)::numeric AS sicor_credito_matriz,
           COALESCE(sm.n_mat,0)           AS sicor_matriz_contratos,
           ia.estab_sem_ia, ia.estab_bovinos,
           COALESCE(fn.n_leads,0)         AS n_leads_nossos,
           COALESCE(tm.n_tecnicos,0)      AS n_tecnicos_nossos,
           v.n_vet,
           -- deserto vet: ausente na MV (sem suprimento) OU n_vet=0
           (v.codigo_ibge IS NULL OR COALESCE(v.n_vet,0)=0) AS deserto_vet
    FROM base b
    LEFT JOIN sic_bov sb ON sb.codigo_ibge=b.codigo_ibge
    LEFT JOIN sic_mat sm ON sm.codigo_ibge=b.codigo_ibge
    LEFT JOIN ia        ON ia.codigo_ibge=b.codigo_ibge
    LEFT JOIN fn_norm fn ON fn.codigo_ibge=b.codigo_ibge
    LEFT JOIN tec_mun tm ON tm.codigo_ibge=b.codigo_ibge
    LEFT JOIN vet v     ON v.codigo_ibge=b.codigo_ibge
),
scored AS (
    SELECT j.*,
           -- normalizações por cume_dist (percentil 0-1) do log1p
           cume_dist() OVER (ORDER BY ln(1+COALESCE(matrizes_estim2024,0)))
               AS n_demanda,
           cume_dist() OVER (ORDER BY ln(1 +
               0.65*sicor_credito_matriz + 0.35*sicor_invest_bovinos_2125))
               AS n_sicor
    FROM joined j
)
SELECT
    codigo_ibge, municipio, uf,
    matrizes_estim2024, bovinos_ppm2024,
    sicor_invest_bovinos_2125, sicor_bovinos_contratos,
    sicor_credito_matriz, sicor_matriz_contratos,
    deserto_vet, n_vet,
    estab_sem_ia, estab_bovinos,
    n_leads_nossos, n_tecnicos_nossos,
    round(n_demanda::numeric, 4) AS n_demanda,
    round(n_sicor::numeric,   4) AS n_sicor,
    round((0.45*n_demanda + 0.35*n_sicor
           + 0.20*(CASE WHEN deserto_vet THEN 1 ELSE 0 END))::numeric, 4)
        AS score_oportunidade,
    -- gap_canal: alta oportunidade SEM nosso canal
    ( (0.45*n_demanda + 0.35*n_sicor
        + 0.20*(CASE WHEN deserto_vet THEN 1 ELSE 0 END)) >= 0.70
      AND n_tecnicos_nossos = 0
      AND cume_dist() OVER (ORDER BY n_leads_nossos) < 0.40
    ) AS gap_canal
FROM scored;

CREATE UNIQUE INDEX idx_terr_oport_ibge
    ON prospeccao.territorio_oportunidade (codigo_ibge);
CREATE INDEX idx_terr_oport_score
    ON prospeccao.territorio_oportunidade (score_oportunidade DESC);
CREATE INDEX idx_terr_oport_gap
    ON prospeccao.territorio_oportunidade (gap_canal) WHERE gap_canal;

GRANT SELECT ON prospeccao.territorio_oportunidade TO wins_app;
