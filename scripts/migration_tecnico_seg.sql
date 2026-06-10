-- migration_tecnico_seg.sql (2026-06-11)
-- Validação/correção do canal técnico (vet/zootecnista).
-- Fix 1: backfill WhatsApp em prospeccao.tecnico_social (celular BR 11-díg = WhatsApp;
--         o enrich_tecnico_social.py não preenchia 'whatsapp' -> ficava 0).
-- Fix 2: v_tecnico_lead ganha densidade vet/100k cabeças e rebaixa municípios
--         urbano-distorcidos (capitais/cidades grandes com franja rural inflavam B/C).
--         Reversível: re-tier numa VIEW, nenhum dado é apagado.

BEGIN;

-- ---- Fix 1: WhatsApp = celular quando for móvel BR de 11 dígitos ----
UPDATE prospeccao.tecnico_social
SET whatsapp = celular
WHERE (whatsapp IS NULL OR whatsapp = '')
  AND celular ~ '^[0-9]{11}$'
  AND substring(celular from 3 for 1) = '9';   -- 3º dígito = 9 (celular)

-- ---- Fix 2: view de segmentação com densidade + downgrade urbano ----
DROP VIEW IF EXISTS prospeccao.v_tecnico_lead;
CREATE VIEW prospeccao.v_tecnico_lead AS
WITH vet_dens AS (
  -- densidade urbana medida pelos estab. de VETERINÁRIA (CNAE 7500100) por município
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
    ELSE NULL::text
  END AS categoria,
  NULLIF(v.ddd_1::text || v.telefone_1::text, ''::text) AS tel,
  NULLIF(v.correio_eletronico, ''::text) AS email,
  h.bovinos AS bovinos_municipio,
  round(d.vets_mun::numeric * 100000 / NULLIF(h.bovinos, 0), 1) AS vets_por_100k_cab,
  (d.vets_mun::numeric * 100000 / NULLIF(h.bovinos, 0)) > 120 AS urbano_distorcido,
  CASE
    -- inseminador (CNAE de maleta) é sinal de corte forte mesmo na cidade -> sempre A
    WHEN v.cnae_fiscal_principal::text = '0162801'::text THEN 'A-inseminador'::text
    -- capital/cidade urbana com franja rural: muitos vets p/ pouco rebanho -> pet provável
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

COMMIT;
