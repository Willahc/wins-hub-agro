-- CSV MASTER Monte Sião (jun/13) — uma linha por fazenda do ICP (pecuária) com TODOS os canais
-- consolidados (WhatsApp/Instagram/e-mail/celular/telefone), decisor+operador, sinal genético,
-- e o CANAL RECOMENDADO + qual script do roteiro usar. Une: lead_decisor, empresa_rural,
-- prospect_genetica, contato_candidatos, resto_referencia, hunter_entrega, icp527/icp_media.
DROP VIEW IF EXISTS prospeccao.master_montesiao;
CREATE VIEW prospeccao.master_montesiao AS
WITH best_email AS (   -- melhor e-mail Hunter por fazenda (valid > catch-all)
  SELECT DISTINCT ON (cnpj_basico) cnpj_basico, email, verif_status,
         CASE WHEN tier_entrega='A-confirmada' THEN 'valid' WHEN tier_entrega='B-catchall' THEN 'catch-all' ELSE tier_entrega END AS email_tier
  FROM prospeccao.hunter_entrega
  ORDER BY cnpj_basico, CASE tier_entrega WHEN 'A-confirmada' THEN 1 WHEN 'B-catchall' THEN 2 ELSE 3 END
), op AS (             -- operador jovem (filho/gestor 31-50)
  SELECT DISTINCT ON (cnpj_basico) cnpj_basico, nome
  FROM prospeccao.contato_candidatos WHERE faixa BETWEEN 3 AND 5
  ORDER BY cnpj_basico, score_alcancavel DESC, faixa
), est AS (            -- CNPJ completo (matriz) + nome fantasia da fazenda
  SELECT DISTINCT ON (cnpj_basico) cnpj_basico,
    substr(lpad(cnpj_basico,8,'0'),1,2)||'.'||substr(lpad(cnpj_basico,8,'0'),3,3)||'.'||substr(lpad(cnpj_basico,8,'0'),6,3)
      ||'/'||lpad(cnpj_ordem,4,'0')||'-'||lpad(cnpj_dv,2,'0') AS cnpj_completo,
    NULLIF(nome_fantasia,'') AS nome_fazenda
  FROM cnpj.estabelecimento_rural
  ORDER BY cnpj_basico, (identificador_matriz_filial='1') DESC, cnpj_ordem
), ch AS (             -- canais consolidados por fazenda
  SELECT ld.cnpj_basico,
    COALESCE(rr.whatsapp, i5.whatsapp, i5.cab_whatsapp, im.cab_whatsapp)        AS whatsapp,
    rr.whats_ufmatch                                                            AS whats_alta_conf,
    COALESCE(i5.celular, i5.cab_cel, im.cab_cel)                                AS celular,
    COALESCE(rr.instagram, i5.instagram, i5.cab_instagram, im.cab_instagram)    AS instagram,
    rr.dominio_cand                                                             AS dominio,
    rr.followers,
    COALESCE(rr.whatsapp, rr.whatsapp_bio)                                       AS whatsapp_qualquer,
    (SELECT NULLIF(e.ddd_1,'')||NULLIF(e.telefone_1,'') FROM cnpj.estabelecimento_rural e
       WHERE e.cnpj_basico=ld.cnpj_basico AND COALESCE(e.telefone_1,'')<>'' LIMIT 1) AS telefone_rfb
  FROM prospeccao.lead_decisor ld
  LEFT JOIN prospeccao.resto_referencia rr ON rr.cnpj_basico=ld.cnpj_basico
  LEFT JOIN prospeccao.icp527_screen      i5 ON i5.cnpj_basico=ld.cnpj_basico
  LEFT JOIN prospeccao.icp_media_screen   im ON im.cnpj_basico=ld.cnpj_basico
)
SELECT
  CASE pg.confianca WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baixa' THEN 3 ELSE 4 END AS prioridade,
  ld.razao, COALESCE(est.nome_fazenda, ld.razao) AS nome_fazenda, est.cnpj_completo,
  ld.uf, ld.municipio,
  ld.decisor_top AS decisor, COALESCE(op.nome, df.socio_jovem) AS operador_jovem,
  COALESCE(df.n_decisores,1) AS n_decisores, df.decisores AS decisores_todos,
  count(*) OVER (PARTITION BY COALESCE(lower(btrim(regexp_replace(ld.decisor_top,'\s*\(.*$',''))), ld.cnpj_basico)) AS dono_n_fazendas,
  round(em.capital_social/1e6,1) AS capital_mi,
  COALESCE(pg.confianca,'-') AS sinal_genetico,
  CASE WHEN pg.confianca IN ('alta','media','baixa') THEN pg.touros_nelore ELSE 0 END AS touros_nelore,
  COALESCE(ch.whatsapp_qualquer, ch.whatsapp) AS whatsapp, ch.whats_alta_conf, ch.celular, ch.instagram,
  ch.followers,
  CASE WHEN ch.followers>=50000 THEN '1.50k+' WHEN ch.followers>=10000 THEN '2.10-50k'
       WHEN ch.followers>=5000 THEN '3.5-10k' WHEN ch.followers>=1000 THEN '4.1-5k'
       WHEN ch.followers IS NOT NULL THEN '5.<1k' ELSE NULL END AS porte_digital,
  be.email AS email, be.email_tier, ch.telefone_rfb, ch.dominio, ld.linkedin,
  -- canal recomendado (cascata por força/custo de contato)
  CASE
    WHEN ch.whats_alta_conf THEN 'WhatsApp'
    WHEN be.email_tier='valid' THEN 'E-mail'
    WHEN COALESCE(ch.whatsapp_qualquer,ch.whatsapp) IS NOT NULL OR ch.celular IS NOT NULL THEN 'WhatsApp/Ligacao'
    WHEN ch.instagram IS NOT NULL THEN 'Instagram DM'
    WHEN be.email_tier='catch-all' THEN 'E-mail (risco bounce)'
    WHEN ch.telefone_rfb IS NOT NULL THEN 'Ligacao (capturar zap)'
    ELSE 'sem canal'
  END AS canal_recomendado,
  -- qual script do ROTEIRO_primeiro_toque.md usar
  CASE
    WHEN ch.whats_alta_conf OR COALESCE(ch.whatsapp_qualquer,ch.whatsapp) IS NOT NULL THEN 'WA'
    WHEN be.email_tier IN ('valid','catch-all') THEN 'EM'
    WHEN ch.instagram IS NOT NULL THEN 'DM'
    WHEN ch.celular IS NOT NULL OR ch.telefone_rfb IS NOT NULL THEN 'TEL'
    ELSE '-'
  END AS script,
  ld.cnpj_basico
FROM prospeccao.lead_decisor ld
JOIN cnpj.empresa_rural em ON em.cnpj_basico=ld.cnpj_basico
LEFT JOIN prospeccao.prospect_genetica pg ON pg.cnpj_basico=ld.cnpj_basico
LEFT JOIN op ON op.cnpj_basico=ld.cnpj_basico
LEFT JOIN best_email be ON be.cnpj_basico=ld.cnpj_basico
LEFT JOIN ch ON ch.cnpj_basico=ld.cnpj_basico
LEFT JOIN est ON est.cnpj_basico=ld.cnpj_basico
LEFT JOIN prospeccao.decisores_fazenda df ON df.cnpj_basico=ld.cnpj_basico
WHERE ld.uf IN ('MT','MS','GO','PA','TO','MG','BA','RO')
  AND em.capital_social < 150000000   -- fora conglomerado
  AND (pg.confianca IN ('alta','media','baixa')
       OR ch.whatsapp IS NOT NULL OR ch.instagram IS NOT NULL
       OR ch.celular IS NOT NULL OR be.email IS NOT NULL);
