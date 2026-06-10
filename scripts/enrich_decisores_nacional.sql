-- Enriquecimento NACIONAL de decisores p/ TODAS as fazendas de corte ativas (Brasil),
-- 100% via dados locais da Receita (cnpj.socio_rural + razão social), sem API.
-- Preserva os já enriquecidos ao vivo (BrasilAPI) e os LinkedIn: ON CONFLICT DO NOTHING.
-- Códigos de qualificação de sócio (RFB): 49=Sócio-Adm, 05=Administrador, 16=Presidente,
-- 10=Diretor, 59=Produtor Rural, 65=Titular, 22=Sócio.

WITH qual(code, label, prio) AS (VALUES
  ('49','Sócio-Administrador',1),('65','Titular',2),('05','Administrador',2),
  ('16','Presidente',3),('59','Produtor Rural',3),('10','Diretor',4),
  ('08','Conselheiro de Administração',5),('22','Sócio',6),('30','Sócio/Acionista',7),
  ('38','Sócio',7),('29','Sócio (exterior)',8),('37','Sócio PJ',9),('63','Cotas em Tesouraria',9)),
corte AS (
  SELECT DISTINCT e.cnpj_basico
  FROM cnpj.estabelecimento_rural e
  WHERE e.cnae_fiscal_principal='0151201' AND e.situacao_cadastral='02'),
-- sócios PESSOA FÍSICA com papel de decisão, ranqueados pelo melhor cargo
soc AS (
  SELECT s.cnpj_basico, s.nome_socio,
         COALESCE(q.label,'Sócio') AS label, COALESCE(q.prio,6) AS prio,
         row_number() OVER (PARTITION BY s.cnpj_basico
                            ORDER BY COALESCE(q.prio,6), s.nome_socio) AS rn
  FROM cnpj.socio_rural s
  JOIN corte c ON c.cnpj_basico = s.cnpj_basico
  LEFT JOIN qual q ON q.code = s.qualificacao_do_socio
  WHERE s.identificador_de_socio <> '1'                    -- exclui sócio PJ
    AND NULLIF(trim(s.nome_socio),'') IS NOT NULL),
top_soc AS (SELECT cnpj_basico, nome_socio||' ('||label||')' AS decisor_top FROM soc WHERE rn=1),
all_soc AS (SELECT cnpj_basico,
                   string_agg(nome_socio||' ('||label||')', '; ' ORDER BY prio) AS decisores
            FROM soc WHERE rn <= 4 GROUP BY cnpj_basico)
INSERT INTO prospeccao.lead_decisor
  (cnpj_basico, cnpj14, razao, uf, municipio, tipo, decisores, decisor_top, situacao_viva, porte, enriched_at)
SELECT c.cnpj_basico, est.cnpj14, est.razao, est.uf, est.municipio,
       'FAMILIAR/ICP',
       COALESCE(a.decisores, est.fallback),
       COALESCE(t.decisor_top, est.fallback),
       'ATIVA (Receita, dump abr/2026)',
       est.porte, now()
FROM corte c
LEFT JOIN top_soc t ON t.cnpj_basico = c.cnpj_basico
LEFT JOIN all_soc a ON a.cnpj_basico = c.cnpj_basico
JOIN LATERAL (
  SELECT DISTINCT ON (e.cnpj_basico)
         e.cnpj_basico||e.cnpj_ordem||e.cnpj_dv AS cnpj14,
         COALESCE(NULLIF(em.razao_social,''), e.nome_fantasia) AS razao,
         e.uf, e.municipio_nome AS municipio, em.porte,
         COALESCE(NULLIF(em.razao_social,''), e.nome_fantasia, '(produtor rural)')||' (produtor rural)' AS fallback
  FROM cnpj.estabelecimento_rural e
  LEFT JOIN cnpj.empresa_rural em ON em.cnpj_basico = e.cnpj_basico
  WHERE e.cnpj_basico = c.cnpj_basico
  ORDER BY e.cnpj_basico, (e.telefone_1 IS NOT NULL) DESC, (e.correio_eletronico IS NOT NULL) DESC
) est ON true
ON CONFLICT (cnpj_basico) DO NOTHING;
