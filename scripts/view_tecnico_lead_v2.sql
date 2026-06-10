-- view_tecnico_lead_v2.sql (2026-06-11) — estende categoria p/ incluir os estab. de CNAE
-- secundário relevante (agro/repro/insumo) como 'repro_secundario'. Pet/escritório seguem NULL
-- (excluídos da fila por categoria IS NOT NULL). Mesmas colunas → CREATE OR REPLACE seguro.
CREATE OR REPLACE VIEW prospeccao.v_tecnico_lead AS
WITH vet_dens AS (
  SELECT municipio_nome, uf,
         count(*) FILTER (WHERE cnae_fiscal_principal::text = '7500100') AS vets_mun
  FROM cnpj.estabelecimento_vet
  WHERE situacao_cadastral::text = '02'
  GROUP BY municipio_nome, uf
)
SELECT v.cnpj_basico,
  (v.cnpj_basico::text || v.cnpj_ordem::text) || v.cnpj_dv::text AS cnpj14,
  COALESCE(NULLIF(v.nome_fantasia, ''::text), '(sem nome fantasia)'::text) AS nome,
  v.municipio_nome AS municipio,
  v.uf,
  CASE v.cnae_fiscal_principal
    WHEN '0162801'::text THEN 'inseminacao'::text
    WHEN '0162899'::text THEN 'apoio_pecuaria'::text
    WHEN '7500100'::text THEN 'veterinaria'::text
    ELSE (CASE WHEN v.cnae_fiscal_principal::text LIKE '01%'
                 OR v.cnae_fiscal_principal::text IN ('4771704','4623108','4623199','4619200','4611700','7490103','7490104')
               THEN 'repro_secundario'::text ELSE NULL::text END)
  END AS categoria,
  NULLIF(v.ddd_1::text || v.telefone_1::text, ''::text) AS tel,
  NULLIF(v.correio_eletronico, ''::text) AS email,
  h.bovinos AS bovinos_municipio,
  round(d.vets_mun::numeric * 100000 / NULLIF(h.bovinos, 0), 1) AS vets_por_100k_cab,
  (d.vets_mun::numeric * 100000 / NULLIF(h.bovinos, 0)) > 120 AS urbano_distorcido,
  CASE
    WHEN v.cnae_fiscal_principal::text = '0162801'::text THEN 'A-inseminador'::text
    WHEN (d.vets_mun::numeric * 100000 / NULLIF(h.bovinos, 0)) > 120 THEN 'U-urbano-distorcido'::text
    WHEN h.bovinos >= 200000 THEN 'B-corte-alto'::text
    WHEN h.bovinos >= 50000 THEN 'C-corte-medio'::text
    WHEN h.bovinos IS NULL OR h.bovinos < 20000 THEN 'E-pet-provavel'::text
    ELSE 'D-corte-baixo'::text
  END AS tier
FROM cnpj.estabelecimento_vet v
  LEFT JOIN prospeccao.mv_herd_mun h
    ON h.nome_norm = upper(unaccent(v.municipio_nome)) AND h.uf = v.uf::text
  LEFT JOIN vet_dens d
    ON d.municipio_nome = v.municipio_nome AND d.uf = v.uf
WHERE v.situacao_cadastral::text = '02';
