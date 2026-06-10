-- v_white_space_pecuaria v2 (2026-06-11): oferta técnica do Deserto Vet sincronizada com os 52k
-- (cnpj.estabelecimento_vet via prospeccao.mv_vet_supply_mun) e ENRIQUECIDA: cnpj_vet agora é a
-- oferta técnica TOTAL (vet+insem+apoio) — quem realmente atende genética/reprodução — não só
-- veterinária pura. Deserto/bovinos_por_vet recomputados sobre o total. +coluna cnpj_vet_clinica.
-- CREATE OR REPLACE: colunas existentes preservadas em nome/tipo/ordem; nova anexada no fim.
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
    COALESCE(vs.n_tecnico, 0)::integer AS cnpj_vet,                 -- oferta técnica TOTAL (vet+insem+apoio), sincronizada c/ os 52k
    COALESCE(vs.n_insem, 0)::integer AS cnpj_inseminacao,
    COALESCE(vs.n_apoio, 0)::integer AS cnpj_manejo,
    CASE WHEN COALESCE(vs.n_tecnico,0) = 0 THEN ppm.bovinos
         ELSE round(ppm.bovinos::numeric / vs.n_tecnico::numeric, 0)::integer::bigint END AS bovinos_por_vet,
    CASE WHEN COALESCE(vs.n_tecnico,0) = 0 THEN 'DESERTO VET'::text
         WHEN vs.n_tecnico < 5 THEN 'BAIXA COBERTURA'::text
         ELSE 'NORMAL'::text END AS classificacao_vet,
    COALESCE(vs.n_vet, 0)::integer AS cnpj_vet_clinica             -- NOVA: só veterinária pura (referência)
 FROM referencia.municipio ref
   LEFT JOIN ppm ON ppm.codigo_ibge = ref.codigo_ibge
   LEFT JOIN mb_pasto mb ON mb.codigo_ibge = ref.codigo_ibge
   LEFT JOIN cnpj_pivot cnpj ON cnpj.codigo_ibge = ref.codigo_ibge
   LEFT JOIN prospeccao.mv_vet_supply_mun vs ON vs.codigo_ibge = ref.codigo_ibge
 WHERE ppm.bovinos IS NOT NULL;
