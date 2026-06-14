-- DESERTO VET v3 (jun/14): demanda-aware + REGIONAL. Substitui a contagem de
-- estabelecimentos DENTRO da divisa por CARGA na área de serviço real do técnico (raio 75km):
--   carga = gado na região / técnicos na região (vet+insem+apoio+manejo, CNPJ ativo).
-- Padrão: >=40.000 cab/técnico (~p90) OU 0 técnico em 75km = DESERTO; 15k-40k = BAIXA;
--   piso de 1.000 cabeças no município exclui não-pecuária (Noronha etc.).
-- Por quê: vet viaja — divisa de município não é fronteira de serviço; e contagem ignora demanda
--   (São Félix do Xingu: 2,4M cab/5 vets era 'NORMAL'). Resultado: menos desertos, muito mais gado.
CREATE EXTENSION IF NOT EXISTS cube;
CREATE EXTENSION IF NOT EXISTS earthdistance;

-- (1) núcleo regional: gado + técnicos somados num raio de 75km do centroide do município
DROP MATERIALIZED VIEW IF EXISTS prospeccao.mv_mun_regional CASCADE;
CREATE MATERIALIZED VIEW prospeccao.mv_mun_regional AS
WITH sup AS (
  SELECT m.codigo_ibge,
    count(*) FILTER (WHERE e.cnae_fiscal_principal::text = ANY (ARRAY['7500100','0162801','0162899','0162803'])) AS n_tec
  FROM cnpj.estabelecimento_vet e
  JOIN referencia.municipio m ON m.codigo_tom = NULLIF(e.municipio::text,'')::integer
  WHERE e.situacao_cadastral::text='02' AND e.municipio::text ~ '^[0-9]+$'
  GROUP BY m.codigo_ibge
),
dem AS (SELECT codigo_ibge_mun::integer codigo_ibge, efetivo_cabecas bovinos
        FROM prospeccao.ppm_municipio WHERE especie_codigo::text='BOV' AND ano_referencia=2023),
muni AS (
  SELECT m.codigo_ibge, m.latitude lat, m.longitude lng,
    COALESCE(d.bovinos,0) bovinos, COALESCE(s.n_tec,0) n_tec
  FROM referencia.municipio m
  LEFT JOIN dem d ON d.codigo_ibge=m.codigo_ibge
  LEFT JOIN sup s ON s.codigo_ibge=m.codigo_ibge
  WHERE m.latitude IS NOT NULL AND m.longitude IS NOT NULL
)
SELECT a.codigo_ibge, a.bovinos AS bov_mun, a.n_tec AS tec_mun,
  sum(b.bovinos)::bigint AS bov_reg, sum(b.n_tec)::int AS tec_reg
FROM muni a JOIN muni b
  ON b.lat BETWEEN a.lat-0.70 AND a.lat+0.70
 AND b.lng BETWEEN a.lng-(0.70/cos(radians(a.lat))) AND a.lng+(0.70/cos(radians(a.lat)))
 AND earth_distance(ll_to_earth(a.lat,a.lng), ll_to_earth(b.lat,b.lng)) <= 75000
GROUP BY a.codigo_ibge, a.bovinos, a.n_tec;
CREATE UNIQUE INDEX ON prospeccao.mv_mun_regional(codigo_ibge);
GRANT SELECT ON prospeccao.mv_mun_regional TO wins_app;

-- (2) v_white_space: mantém colunas existentes; classificacao_vet passa a ser REGIONAL;
--     anexa carga_regional / tecnicos_75km / bovinos_75km no fim (transparência).
CREATE OR REPLACE VIEW prospeccao.v_white_space_pecuaria AS
 WITH ppm AS (
     SELECT ppm_municipio.codigo_ibge_mun::integer AS codigo_ibge, ppm_municipio.efetivo_cabecas AS bovinos
     FROM prospeccao.ppm_municipio
     WHERE ppm_municipio.especie_codigo::text = 'BOV'::text AND ppm_municipio.ano_referencia = 2023
 ), mb_pasto AS (
     SELECT m.codigo_ibge, sum(mb_1.area_ha)::integer AS pasto_ha
     FROM cobertura.mapbiomas_municipio mb_1
       JOIN referencia.municipio m ON m.nome_normalizado::text = referencia.normalizar_nome(mb_1.municipio) AND m.uf::text = mb_1.state_acronym::text
     WHERE mb_1.ano = 2024 AND mb_1.class_id = 15
     GROUP BY m.codigo_ibge
 ), cnpj_pivot AS (
     SELECT m.codigo_ibge, c.bovino_corte, c.bovino_leite
     FROM cnpj.cnpj_por_municipio c
       JOIN referencia.municipio m ON m.codigo_tom = c.codigo_municipio::integer
 )
 SELECT ref.nome, ref.uf, ref.codigo_ibge, ref.latitude, ref.longitude,
    ppm.bovinos, mb.pasto_ha,
    CASE WHEN mb.pasto_ha > 0 THEN round(ppm.bovinos::numeric / mb.pasto_ha::numeric, 2) ELSE NULL::numeric END AS lotacao_cab_ha,
    COALESCE(cnpj.bovino_corte, 0) AS cnpj_bov_corte,
    COALESCE(cnpj.bovino_leite, 0) AS cnpj_bov_leite,
    COALESCE(vs.n_tecnico, 0)::integer AS cnpj_vet,
    COALESCE(vs.n_insem, 0)::integer AS cnpj_inseminacao,
    COALESCE(vs.n_apoio, 0)::integer AS cnpj_manejo,
    CASE WHEN COALESCE(vs.n_tecnico,0) = 0 THEN ppm.bovinos
         ELSE round(ppm.bovinos::numeric / vs.n_tecnico::numeric, 0)::integer::bigint END AS bovinos_por_vet,
    -- classificação REGIONAL (raio 75km, carga gado/técnico) — substitui a contagem na divisa
    CASE WHEN ppm.bovinos < 1000 THEN 'NORMAL'::text
         WHEN COALESCE(reg.tec_reg,0) = 0 THEN 'DESERTO VET'::text
         WHEN reg.bov_reg::numeric / reg.tec_reg >= 40000 THEN 'DESERTO VET'::text
         WHEN reg.bov_reg::numeric / reg.tec_reg >= 15000 THEN 'BAIXA COBERTURA'::text
         ELSE 'NORMAL'::text END AS classificacao_vet,
    COALESCE(vs.n_vet, 0)::integer AS cnpj_vet_clinica,
    -- NOVAS (transparência regional):
    COALESCE(reg.tec_reg,0) AS tecnicos_75km,
    COALESCE(reg.bov_reg,0) AS bovinos_75km,
    CASE WHEN COALESCE(reg.tec_reg,0) > 0 THEN round(reg.bov_reg::numeric / reg.tec_reg)::bigint END AS carga_regional
 FROM referencia.municipio ref
   LEFT JOIN ppm ON ppm.codigo_ibge = ref.codigo_ibge
   LEFT JOIN mb_pasto mb ON mb.codigo_ibge = ref.codigo_ibge
   LEFT JOIN cnpj_pivot cnpj ON cnpj.codigo_ibge = ref.codigo_ibge
   LEFT JOIN prospeccao.mv_vet_supply_mun vs ON vs.codigo_ibge = ref.codigo_ibge
   LEFT JOIN prospeccao.mv_mun_regional reg ON reg.codigo_ibge = ref.codigo_ibge
 WHERE ppm.bovinos IS NOT NULL;

-- (3) fazenda_deserto: join por codigo_ibge (via normalizar_nome) — recupera os ~195 que
--     o join por nome cru perdia.
DROP TABLE IF EXISTS prospeccao.fazenda_deserto;
CREATE TABLE prospeccao.fazenda_deserto AS
SELECT f.cnpj_basico, w.classificacao_vet
FROM prospeccao.fazenda_nacional f
JOIN referencia.municipio m ON m.nome_normalizado::text = referencia.normalizar_nome(f.municipio) AND m.uf::text = f.uf
JOIN prospeccao.v_white_space_pecuaria w ON w.codigo_ibge = m.codigo_ibge;
CREATE INDEX ON prospeccao.fazenda_deserto(cnpj_basico);
CREATE INDEX ON prospeccao.fazenda_deserto(classificacao_vet);
GRANT SELECT ON prospeccao.fazenda_deserto TO wins_app;

-- (4) fazenda_ibge: mapa fazenda->codigo_ibge (+geo) p/ busca por raio rápida
--     (ficha do técnico / fazendas no raio de 75km). Evita normalizar_nome a cada request.
DROP TABLE IF EXISTS prospeccao.fazenda_ibge;
CREATE TABLE prospeccao.fazenda_ibge AS
SELECT f.cnpj_basico, m.codigo_ibge, m.latitude, m.longitude
FROM prospeccao.fazenda_nacional f
JOIN referencia.municipio m ON m.nome_normalizado::text = referencia.normalizar_nome(f.municipio) AND m.uf::text = f.uf;
CREATE INDEX ON prospeccao.fazenda_ibge(codigo_ibge);
CREATE UNIQUE INDEX ON prospeccao.fazenda_ibge(cnpj_basico);
GRANT SELECT ON prospeccao.fazenda_ibge TO wins_app;
