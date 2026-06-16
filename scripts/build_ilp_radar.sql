-- RADAR ILP (Integração Lavoura-Pecuária) — jun/16
-- Identifica pecuaristas em zonas de conversão pasto->lavoura = leads premium p/ inputs
-- agrícolas (BASF/xarvio): quem está virando agricultor compra defensivo/semente do zero.
-- Fonte: cobertura.mapbiomas_municipio (série 2010/2020/2024, classe 3.1 Pasture vs 3.2 Agriculture).
-- Idempotente (DROP/CREATE). Ver [[wins-agro-basf-inputs-gtm]].

DROP MATERIALIZED VIEW IF EXISTS prospeccao.ilp_municipio CASCADE;
CREATE MATERIALIZED VIEW prospeccao.ilp_municipio AS
WITH mb AS (
  SELECT upper(unaccent(municipio)) AS nome_norm, state_acronym AS uf,
    sum(area_ha) FILTER (WHERE class_level_2='3.1. Pasture'        AND ano=2010) AS pasto_2010,
    sum(area_ha) FILTER (WHERE class_level_2='3.1. Pasture'        AND ano=2024) AS pasto_2024,
    sum(area_ha) FILTER (WHERE class_level_2='3.2. Agriculture'    AND ano=2010) AS agri_2010,
    sum(area_ha) FILTER (WHERE class_level_2='3.2. Agriculture'    AND ano=2020) AS agri_2020,
    sum(area_ha) FILTER (WHERE class_level_2='3.2. Agriculture'    AND ano=2024) AS agri_2024,
    sum(area_ha) FILTER (WHERE class_level_2='3.4. Mosaic of Uses' AND ano=2024) AS mosaic_2024
  FROM cobertura.mapbiomas_municipio
  WHERE ano IN (2010,2020,2024)
  GROUP BY 1,2),
calc AS (
  SELECT mb.*,
    COALESCE(agri_2024,0)-COALESCE(agri_2010,0) AS delta_agri,
    COALESCE(agri_2024,0)-COALESCE(agri_2020,0) AS delta_agri_recente,
    COALESCE(pasto_2024,0)-COALESCE(pasto_2010,0) AS delta_pasto
  FROM mb
  WHERE COALESCE(pasto_2010,0) > 5000),               -- só território pecuário de verdade
scored AS (
  SELECT c.*, r.codigo_ibge,
    round((0.40*cume_dist() OVER (ORDER BY GREATEST(delta_agri,0))
         + 0.30*cume_dist() OVER (ORDER BY GREATEST(delta_agri_recente,0))
         + 0.30*cume_dist() OVER (ORDER BY COALESCE(pasto_2024,0)))::numeric, 3) AS ilp_score
  FROM calc c
  LEFT JOIN referencia.municipio r ON r.nome_normalizado=c.nome_norm AND r.uf=c.uf)
SELECT nome_norm, uf, codigo_ibge,
  round(pasto_2010) pasto_2010_ha, round(pasto_2024) pasto_2024_ha,
  round(agri_2010) agri_2010_ha, round(agri_2024) agri_2024_ha,
  round(delta_agri) delta_agri_ha, round(delta_agri_recente) delta_agri_recente_ha,
  round(delta_pasto) delta_pasto_ha, round(COALESCE(mosaic_2024,0)) mosaic_2024_ha,
  ilp_score,
  (delta_agri_recente > 1000 AND pasto_2024 > 20000) AS ilp_ativa   -- lavoura acelerando em base pecuária
FROM scored;
CREATE INDEX ON prospeccao.ilp_municipio (codigo_ibge);
CREATE INDEX ON prospeccao.ilp_municipio (ilp_score DESC);
CREATE INDEX ON prospeccao.ilp_municipio (nome_norm, uf);
GRANT SELECT ON prospeccao.ilp_municipio TO wins_app;

-- Lista de leads: nossos GRANDES grupos pecuários nos municípios de ILP ativa.
CREATE OR REPLACE VIEW prospeccao.ilp_lead AS
SELECT i.ilp_score, i.uf, f.municipio,
  f.nome_fazenda, f.razao, f.cnpj_completo, f.decisor, f.capital_mi, f.dono_n_fazendas,
  f.whatsapp, f.email, f.canal_recomendado,
  i.delta_agri_recente_ha, i.delta_pasto_ha, i.pasto_2024_ha AS pasto_resta_ha,
  i.codigo_ibge, f.cnpj_basico
FROM prospeccao.fazenda_nacional f
JOIN prospeccao.ilp_municipio i
  ON upper(unaccent(f.municipio))=i.nome_norm AND f.uf=i.uf
WHERE i.ilp_ativa
  AND (COALESCE(f.capital_mi,0) >= 5 OR COALESCE(f.dono_n_fazendas,0) >= 2)
ORDER BY i.ilp_score DESC, f.capital_mi DESC NULLS LAST;
GRANT SELECT ON prospeccao.ilp_lead TO wins_app;
