-- =============================================================================
-- acender_fazenda_matriz.sql
-- WiNS Hub Agro — prospeccao
--
-- Popula prospeccao.fazenda_area a partir do pasto por fazenda computado via
-- MapBiomas (imovel_rural.area_pasto_ha — ver scripts/pasto_por_fazenda_br.py),
-- ACENDENDO a view prospeccao.v_fazenda_matriz (atribuir_matrizes_fazenda.sql).
--
-- area_ha = area_pasto_ha (classe 15, pasto plantado) — o driver certo p/
--   distribuir matrizes/bovinos (gado pasta em pasto, não em soja/floresta).
-- Só fazendas com pasto > 0 (CHECK area_ha > 0; farm sem pasto = 0 matriz).
-- SEM cnpj_basico/CPF: só codigo_car (identifica o imóvel, não a pessoa) — LGPD.
--
-- Idempotente: limpa as linhas de origem MapBiomas e reinsere.
-- Uso (host, porta publicada):
--   PGPASSWORD=... psql -h 127.0.0.1 -U postgres -d wins_agro -f scripts/acender_fazenda_matriz.sql
-- =============================================================================
BEGIN;

DELETE FROM prospeccao.fazenda_area WHERE fonte_geomatch = 'MAPBIOMAS_C15';

INSERT INTO prospeccao.fazenda_area (codigo_car, codigo_ibge, area_ha, fonte_geomatch)
SELECT codigo_car, codigo_ibge_mun::integer, area_pasto_ha, 'MAPBIOMAS_C15'
FROM prospeccao.imovel_rural
WHERE area_pasto_ha > 0 AND codigo_ibge_mun ~ '^[0-9]+$';

COMMIT;

ANALYZE prospeccao.fazenda_area;

\echo '=== fazenda_area populada (esperado ~5,8M) ==='
SELECT count(*) AS fazendas, round(sum(area_ha)/1e6,1) AS mha_pasto
FROM prospeccao.fazenda_area;

\echo '=== nacional: fazendas com atribuição confiável (cobertura>=0.70) ==='
SELECT count(*) FILTER (WHERE confiavel_absoluto) AS confiaveis, count(*) AS total
FROM prospeccao.v_fazenda_matriz;
