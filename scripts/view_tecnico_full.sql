-- view_tecnico_full.sql (2026-06-11)
-- Tabela-produto do canal técnico: 1 linha por estabelecimento de vet ATIVO, juntando
--   nome real PF (vet_nome) + segmentação/tier (v_tecnico_lead) + contato RFB (estabelecimento_vet)
--   + enriquecimento social/CRMV (tecnico_social). É a fila de prospecção pronta p/ entregar.
DROP VIEW IF EXISTS prospeccao.v_tecnico_full;
CREATE VIEW prospeccao.v_tecnico_full AS
SELECT
  vl.cnpj14,
  vl.cnpj_basico,
  -- nome real PF, sem o prefixo de CPF que a RFB põe em Empresário Individual ("057.291.917 FULANO")
  CASE WHEN COALESCE(vn.nome_pf, vl.nome) ~ '[A-Za-z]'
       THEN NULLIF(trim(regexp_replace(COALESCE(vn.nome_pf, vl.nome), '^[0-9.\-/ ]+', '')), '')
       ELSE COALESCE(vn.nome_pf, vl.nome) END    AS nome,
  vn.fonte_nome,                                                     -- razao_EI | socio | razao_fallback
  vl.categoria,                                                      -- inseminacao | veterinaria | apoio_pecuaria
  vl.tier,                                                           -- A-inseminador ... U-urbano-distorcido
  vl.municipio, vl.uf,
  -- contato RFB (da empresa)
  vl.tel                                        AS tel_receita,
  vl.email                                      AS email_receita,
  -- enriquecimento Serper (do profissional)
  ts.whatsapp, ts.celular, ts.instagram, ts.site,
  COALESCE(ts.tel_kg, vl.tel)                   AS tel_melhor,
  -- credencial CRMV (crmv_confiavel=false quando a UF do registro não bate com a do vet)
  ts.crmv, ts.crmv_uf, ts.crmv_cat,
  (ts.crmv IS NOT NULL AND (ts.crmv_uf IS NULL OR ts.crmv_uf = vl.uf)) AS crmv_confiavel,
  ts.profissao,                                                      -- zootecnista | veterinario | ambos | '' (sinal Serper/CRMV)
  -- qualificação
  COALESCE(ts.sinal,'(nao enriquecido)')        AS sinal_corte,
  vl.bovinos_municipio, vl.vets_por_100k_cab,
  (ts.cnpj_basico IS NOT NULL)                  AS enriquecido_serper
FROM prospeccao.v_tecnico_lead vl
LEFT JOIN prospeccao.vet_nome      vn ON vn.cnpj_basico = vl.cnpj_basico
LEFT JOIN prospeccao.tecnico_social ts ON ts.cnpj_basico = vl.cnpj_basico;
