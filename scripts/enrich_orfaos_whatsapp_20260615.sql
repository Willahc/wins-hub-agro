-- =============================================================================
-- Enriquecimento QSA dos órfãos de WhatsApp — 2026-06-15 — 100% SQL local, ZERO API.
-- Alvo: CNPJs em whatsapp_rfb SEM linha em lead_decisor, ATIVOS (situacao '02') e
--       NÃO-vet (exclui CNAE 7500100 = clínica/pet, ruído p/ o canal de produtor).
-- Decisor derivado de cnpj.socio_rural (mesma lógica do enrich_decisores_nacional).
-- tipo='WHATSAPP-ORFAO' marca a proveniência. ON CONFLICT DO NOTHING (idempotente).
-- Reverter: DELETE FROM prospeccao.lead_decisor WHERE tipo='WHATSAPP-ORFAO';
-- =============================================================================
BEGIN;

WITH qual(code, label, prio) AS (VALUES
  ('49','Sócio-Administrador',1),('65','Titular',2),('05','Administrador',2),
  ('16','Presidente',3),('59','Produtor Rural',3),('10','Diretor',4),
  ('08','Conselheiro de Administração',5),('22','Sócio',6),('30','Sócio/Acionista',7),
  ('38','Sócio',7),('29','Sócio (exterior)',8),('37','Sócio PJ',9),('63','Cotas em Tesouraria',9)),
-- alvo: órfão de WhatsApp, ativo, não-vet
alvo AS (
  SELECT DISTINCT e.cnpj_basico
  FROM prospeccao.whatsapp_rfb w
  JOIN cnpj.estabelecimento_rural e ON e.cnpj_basico = w.cnpj_basico
  WHERE NOT EXISTS (SELECT 1 FROM prospeccao.lead_decisor ld WHERE ld.cnpj_basico = w.cnpj_basico)
    AND e.situacao_cadastral = '02'
    AND e.cnae_fiscal_principal <> '7500100'),
soc AS (
  SELECT s.cnpj_basico, s.nome_socio,
         COALESCE(q.label,'Sócio') AS label, COALESCE(q.prio,6) AS prio,
         row_number() OVER (PARTITION BY s.cnpj_basico
                            ORDER BY COALESCE(q.prio,6), s.nome_socio) AS rn
  FROM cnpj.socio_rural s
  JOIN alvo a ON a.cnpj_basico = s.cnpj_basico
  LEFT JOIN qual q ON q.code = s.qualificacao_do_socio
  WHERE s.identificador_de_socio <> '1'
    AND NULLIF(trim(s.nome_socio),'') IS NOT NULL),
top_soc AS (SELECT cnpj_basico, nome_socio||' ('||label||')' AS decisor_top FROM soc WHERE rn=1),
all_soc AS (SELECT cnpj_basico,
                   string_agg(nome_socio||' ('||label||')', '; ' ORDER BY prio) AS decisores
            FROM soc WHERE rn <= 4 GROUP BY cnpj_basico)
INSERT INTO prospeccao.lead_decisor
  (cnpj_basico, cnpj14, razao, uf, municipio, tipo, decisores, decisor_top, situacao_viva, porte, enriched_at)
SELECT a.cnpj_basico, est.cnpj14, est.razao, est.uf, est.municipio,
       'WHATSAPP-ORFAO',
       COALESCE(s.decisores, est.fallback),
       COALESCE(t.decisor_top, est.fallback),
       'ATIVA (Receita, dump abr/2026)',
       est.porte, now()
FROM alvo a
LEFT JOIN top_soc t ON t.cnpj_basico = a.cnpj_basico
LEFT JOIN all_soc s ON s.cnpj_basico = a.cnpj_basico
JOIN LATERAL (
  SELECT DISTINCT ON (e.cnpj_basico)
         e.cnpj_basico||e.cnpj_ordem||e.cnpj_dv AS cnpj14,
         COALESCE(NULLIF(em.razao_social,''), e.nome_fantasia) AS razao,
         e.uf, e.municipio_nome AS municipio, em.porte,
         COALESCE(NULLIF(em.razao_social,''), e.nome_fantasia, '(produtor rural)')||' (produtor rural)' AS fallback
  FROM cnpj.estabelecimento_rural e
  LEFT JOIN cnpj.empresa_rural em ON em.cnpj_basico = e.cnpj_basico
  WHERE e.cnpj_basico = a.cnpj_basico
  ORDER BY e.cnpj_basico, (e.telefone_1 IS NOT NULL) DESC, (e.correio_eletronico IS NOT NULL) DESC
) est ON true
ON CONFLICT (cnpj_basico) DO NOTHING;

COMMIT;
