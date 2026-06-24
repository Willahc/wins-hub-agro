-- =============================================================================
-- acender_fazenda_matriz.sql
-- WiNS Hub Agro — prospeccao
--
-- Popula prospeccao.fazenda_area a partir da ÁREA DE PASTEJO por fazenda computada
-- via MapBiomas (imovel_rural — ver scripts/pasto_full_br.py),
-- ACENDENDO a view prospeccao.v_fazenda_matriz (atribuir_matrizes_fazenda.sql).
--
-- area_ha = area_pasto_ha (classe 15, pasto plantado) + area_campo_ha (classe 12,
--   campo nativo) = ÁREA DE PASTEJO real. Incluir o campo nativo corrige a
--   subatribuição em RS/Pampa, MS/Pantanal e cerrados de campo, onde o gado pasta
--   em campo natural (não em pasto plantado). É o driver certo p/ distribuir
--   matrizes/bovinos (gado não pasta em soja/floresta).
-- Só fazendas com pastejo > 0 (CHECK area_ha > 0; sem pastejo = 0 matriz).
-- SEM cnpj_basico/CPF: só codigo_car (identifica o imóvel, não a pessoa) — LGPD.
--
-- Idempotente: limpa as linhas de origem MapBiomas e reinsere.
-- Uso (host, porta publicada):
--   PGPASSWORD=... psql -h 127.0.0.1 -U postgres -d wins_agro -f scripts/acender_fazenda_matriz.sql
-- =============================================================================
BEGIN;

DELETE FROM prospeccao.fazenda_area WHERE fonte_geomatch IN ('MAPBIOMAS_C15','MAPBIOMAS_PASTEJO');

INSERT INTO prospeccao.fazenda_area (codigo_car, codigo_ibge, area_ha, fonte_geomatch)
SELECT codigo_car, codigo_ibge_mun::integer,
       COALESCE(area_pasto_ha,0) + COALESCE(area_campo_ha,0), 'MAPBIOMAS_PASTEJO'
FROM prospeccao.imovel_rural
WHERE COALESCE(area_pasto_ha,0) + COALESCE(area_campo_ha,0) > 0
  AND codigo_ibge_mun ~ '^[0-9]+$';

COMMIT;

ANALYZE prospeccao.fazenda_area;

\echo '=== fazenda_area populada (esperado ~5,8M) ==='
SELECT count(*) AS fazendas, round(sum(area_ha)/1e6,1) AS mha_pasto
FROM prospeccao.fazenda_area;

\echo '=== nacional: fazendas com atribuição confiável (cobertura>=0.70) ==='
SELECT count(*) FILTER (WHERE confiavel_absoluto) AS confiaveis, count(*) AS total
FROM prospeccao.v_fazenda_matriz;
