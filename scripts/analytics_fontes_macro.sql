-- analytics views: macro/timing signals from the 5 new prospeccao sources
-- read-only over prospeccao.*; GRANT SELECT to wins_app. NÃO commit.
SET search_path = analytics, public;

-- 1) Abate de vacas por UF (PTAA) — sinal de liquidação/reposição de matrizes
CREATE OR REPLACE VIEW analytics.vw_abate_vacas_uf AS
WITH base AS (
    SELECT uf, ano, trimestre, periodo, cabecas
    FROM prospeccao.ptaa_abate_uf
    WHERE categoria = 'Vaca'
),
total AS (
    SELECT uf, ano, trimestre, sum(cabecas) AS abate_total
    FROM prospeccao.ptaa_abate_uf
    GROUP BY uf, ano, trimestre
)
SELECT
    b.uf,
    b.ano,
    b.trimestre,
    b.periodo,
    b.cabecas                                   AS vacas_abatidas,
    t.abate_total,
    round(100.0 * b.cabecas / NULLIF(t.abate_total,0), 1) AS pct_femea_no_abate,
    -- variação YoY (mesmo trimestre, ano anterior) = aceleração da liquidação
    b.cabecas - lag(b.cabecas) OVER (PARTITION BY b.uf, b.trimestre ORDER BY b.ano) AS yoy_delta,
    round(100.0 * (b.cabecas - lag(b.cabecas) OVER (PARTITION BY b.uf, b.trimestre ORDER BY b.ano))
          / NULLIF(lag(b.cabecas) OVER (PARTITION BY b.uf, b.trimestre ORDER BY b.ano),0), 1) AS yoy_pct
FROM base b
JOIN total t USING (uf, ano, trimestre)
ORDER BY b.uf, b.ano, b.trimestre;

-- 2) Crédito pecuário SICOR por UF — bovinos (1300) e matrizes/reprodutores (7580)
CREATE OR REPLACE VIEW analytics.vw_credito_pecuario_uf AS
WITH agg AS (
    SELECT uf, ano,
        sum(vl_total_brl) FILTER (WHERE cd_produto = '1300') AS bovinos_brl,
        sum(n_contratos)  FILTER (WHERE cd_produto = '1300') AS bovinos_contratos,
        sum(vl_total_brl) FILTER (WHERE cd_produto = '7580') AS matrizes_brl,
        sum(n_contratos)  FILTER (WHERE cd_produto = '7580') AS matrizes_contratos
    FROM prospeccao.sicor_credito_municipio
    WHERE cd_produto IN ('1300','7580') AND uf IS NOT NULL
    GROUP BY uf, ano
)
SELECT
    uf, ano,
    round(coalesce(bovinos_brl,0),2)  AS bovinos_brl,
    bovinos_contratos,
    round(coalesce(matrizes_brl,0),2) AS matrizes_brl,
    matrizes_contratos,
    -- tendência YoY do investimento total em bovinos
    round(100.0 * (coalesce(bovinos_brl,0) - lag(bovinos_brl) OVER (PARTITION BY uf ORDER BY ano))
          / NULLIF(lag(bovinos_brl) OVER (PARTITION BY uf ORDER BY ano),0), 1) AS bovinos_yoy_pct,
    round(100.0 * (coalesce(matrizes_brl,0) - lag(matrizes_brl) OVER (PARTITION BY uf ORDER BY ano))
          / NULLIF(lag(matrizes_brl) OVER (PARTITION BY uf ORDER BY ano),0), 1) AS matrizes_yoy_pct
FROM agg
ORDER BY uf, ano;

-- 3) Players de genética (exportadores de sêmen)
--    parte A: UF — sêmen bovino puro NCM 05111000 (FOB acumulado)
--    parte B: municípios HS4 0511 alto-FOB / baixa-tonelagem (centrais de elite)
CREATE OR REPLACE VIEW analytics.vw_players_genetica AS
-- A) nível UF: sêmen bovino congelado puro
SELECT
    'UF_SEMEN_PURO'::text                          AS tipo,
    c.uf,
    NULL::integer                                  AS codigo_ibge,
    c.uf                                            AS local,
    sum(c.vl_fob_usd)::numeric(18,2)               AS fob_usd_acum,
    sum(c.kg)::numeric(18,2)                        AS kg_acum,
    round((sum(c.vl_fob_usd)/NULLIF(sum(c.kg),0))::numeric, 0) AS usd_por_kg,
    min(c.ano)                                      AS ano_ini,
    max(c.ano)                                      AS ano_fim
FROM prospeccao.comex_export_municipio c
WHERE c.nivel = 'UF' AND c.ncm = '05111000'
GROUP BY c.uf
UNION ALL
-- B) nível MUNICIPIO: HS4 0511, alto valor e baixa tonelagem (proxy de central de genética)
SELECT
    'MUNICIPIO_ELITE'::text                        AS tipo,
    c.uf,
    max(c.codigo_ibge)                             AS codigo_ibge,
    c.municipio                                     AS local,
    sum(c.vl_fob_usd)::numeric(18,2)               AS fob_usd_acum,
    sum(c.kg)::numeric(18,2)                        AS kg_acum,
    round((sum(c.vl_fob_usd)/NULLIF(sum(c.kg),0))::numeric, 0) AS usd_por_kg,
    min(c.ano)                                      AS ano_ini,
    max(c.ano)                                      AS ano_fim
FROM prospeccao.comex_export_municipio c
WHERE c.nivel = 'MUNICIPIO' AND c.ncm = '0511'
GROUP BY c.municipio, c.uf
HAVING sum(c.vl_fob_usd) > 100000             -- relevância comercial
   AND sum(c.kg) < 50000                      -- baixa tonelagem => sêmen/embrião de elite, não subproduto a granel
ORDER BY tipo, fob_usd_acum DESC;

-- 4) Data-health das 5 fontes novas
CREATE OR REPLACE VIEW analytics.vw_fontes_data_health AS
SELECT 'ptaa_abate_uf' AS fonte, count(*) AS linhas,
       NULL::numeric AS pct_ibge_resolvido,
       min(ano) AS ano_min, max(ano) AS ano_max, max(updated_at) AS atualizado_em,
       'nível UF (sem codigo_ibge)'::text AS nota
FROM prospeccao.ptaa_abate_uf
UNION ALL
SELECT 'sigsif_abate_categoria_uf', count(*),
       round(100.0*count(*) FILTER (WHERE codigo_ibge IS NOT NULL)/NULLIF(count(*),0),1),
       min(ano), max(ano), max(updated_at),
       'abate touros descarte; janela 2002-2020'::text
FROM prospeccao.sigsif_abate_categoria_uf
UNION ALL
SELECT 'sicor_credito_municipio', count(*),
       round(100.0*count(*) FILTER (WHERE codigo_ibge IS NOT NULL)/NULLIF(count(*),0),1),
       min(ano), max(ano), max(updated_at),
       'crédito rural BCB'::text
FROM prospeccao.sicor_credito_municipio
UNION ALL
SELECT 'comex_export_municipio', count(*),
       round(100.0*count(*) FILTER (WHERE codigo_ibge IS NOT NULL)/NULLIF(count(*),0),1),
       min(ano), max(ano), max(updated_at),
       'UF=semen puro 05111000; MUNICIPIO=HS4 0511'::text
FROM prospeccao.comex_export_municipio
UNION ALL
SELECT 'rebanho_municipio', count(*),
       round(100.0*count(*) FILTER (WHERE codigo_ibge IS NOT NULL)/NULLIF(count(*),0),1),
       NULL, NULL, max(updated_at),
       'estoque (Censo2017 + PPM2024), sem dimensão de tempo'::text
FROM prospeccao.rebanho_municipio
UNION ALL
SELECT 'censo2017_ia_municipio', count(*),
       round(100.0*count(*) FILTER (WHERE codigo_ibge IS NOT NULL)/NULLIF(count(*),0),1),
       NULL, NULL, max(updated_at),
       'adoção de IA (leite) por município, snapshot Censo'::text
FROM prospeccao.censo2017_ia_municipio
ORDER BY fonte;

GRANT SELECT ON analytics.vw_abate_vacas_uf,
               analytics.vw_credito_pecuario_uf,
               analytics.vw_players_genetica,
               analytics.vw_fontes_data_health
        TO wins_app;
