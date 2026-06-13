-- VIEW NACIONAL (jun/13): TODAS as 146.298 fazendas de corte do Brasil com decisor + canais.
-- MATERIALIZED. Inclui GUARDA DE QUALIDADE: WhatsApp compartilhado por 4+ DONOS distintos é
-- número genérico (contador) → nulado (não é o contato da fazenda). 1-3 donos = mesmo grupo/família, mantém.
DROP MATERIALIZED VIEW IF EXISTS prospeccao.fazenda_nacional;
CREATE MATERIALIZED VIEW prospeccao.fazenda_nacional AS
WITH est AS (
  SELECT DISTINCT ON (cnpj_basico) cnpj_basico, NULLIF(nome_fantasia,'') AS nome_fazenda,
    substr(lpad(cnpj_basico,8,'0'),1,2)||'.'||substr(lpad(cnpj_basico,8,'0'),3,3)||'.'||substr(lpad(cnpj_basico,8,'0'),6,3)
      ||'/'||lpad(cnpj_ordem,4,'0')||'-'||lpad(cnpj_dv,2,'0') AS cnpj_completo,
    NULLIF(ddd_1,'')||NULLIF(telefone_1,'') AS telefone_rfb
  FROM cnpj.estabelecimento_rural
  ORDER BY cnpj_basico, (identificador_matriz_filial='1') DESC, (COALESCE(telefone_1,'')<>'') DESC, cnpj_ordem),
op AS (SELECT DISTINCT ON (cnpj_basico) cnpj_basico, nome FROM prospeccao.contato_candidatos
       WHERE faixa BETWEEN 3 AND 5 ORDER BY cnpj_basico, score_alcancavel DESC, faixa),
be AS (SELECT DISTINCT ON (cnpj_basico) cnpj_basico, email,
         CASE WHEN tier_entrega='A-confirmada' THEN 'valid' WHEN tier_entrega='B-catchall' THEN 'catch-all' END email_tier
       FROM prospeccao.hunter_entrega WHERE tier_entrega IN ('A-confirmada','B-catchall')
       ORDER BY cnpj_basico, CASE tier_entrega WHEN 'A-confirmada' THEN 1 ELSE 2 END),
-- e-mail da Receita (correio_eletronico): 108k das 146k têm. ~77% são pessoais
-- (hotmail/gmail/terra/uol = caixa do próprio produtor); ~23% são de contador/escritório.
-- Classifica os dois pra não jogar o contador no mesmo balaio do produtor.
erfb AS (SELECT DISTINCT ON (cnpj_basico) cnpj_basico, lower(btrim(correio_eletronico)) AS email_rfb,
           CASE WHEN correio_eletronico ~* 'cont(abil|ador|abilidade)|escritorio|assessoria|fiscal|@.*contab'
                THEN 'rfb-contador' ELSE 'rfb' END AS email_rfb_tier
         FROM cnpj.estabelecimento_rural WHERE correio_eletronico ~* '^[^@ ]+@[^@ ]+\.[^@ ]+$'
         ORDER BY cnpj_basico, (identificador_matriz_filial='1') DESC, cnpj_ordem),
df AS (SELECT cnpj_basico, n_decisores, socio_jovem FROM prospeccao.decisores_fazenda),
base AS (
  SELECT ld.cnpj_basico, ld.uf, ld.municipio, ld.decisor_top, ld.razao, ld.linkedin,
    lower(btrim(regexp_replace(ld.decisor_top,'\s*\(.*$',''))) AS dono_norm,
    COALESCE(est.nome_fazenda, ld.razao) AS nome_fazenda, est.cnpj_completo, est.telefone_rfb,
    COALESCE(op.nome, df.socio_jovem) AS operador_jovem, COALESCE(df.n_decisores,1) AS n_decisores,
    round(em.capital_social/1e6,1) AS capital_mi, COALESCE(pg.confianca,'-') AS sinal_genetico,
    CASE pg.confianca WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baixa' THEN 3 WHEN 'descartar' THEN 4 ELSE 5 END AS prioridade,
    CASE WHEN pg.confianca IN ('alta','media','baixa') THEN pg.touros_nelore ELSE 0 END AS touros_nelore,
    rr.whats_ufmatch AS whats_alta_conf, rr.followers,
    COALESCE(rr.whatsapp, rr.whatsapp_bio, i5.whatsapp, i5.cab_whatsapp, im.cab_whatsapp, cg.whatsapp_grupo, wr.whatsapp) AS wa_raw,
    COALESCE(i5.celular, i5.cab_cel, im.cab_cel) AS celular,
    COALESCE(rr.instagram, i5.instagram, i5.cab_instagram, im.cab_instagram, cg.instagram_grupo) AS instagram,
    -- e-mail: prioriza o confirmado (Hunter), cai pro da Receita quando não há.
    COALESCE(be.email, erfb.email_rfb) AS email,
    COALESCE(be.email_tier, erfb.email_rfb_tier) AS email_tier,
    rr.dominio_cand AS dominio,
    (ct.cnpj_basico IS NOT NULL) AS tem_tecnico
  FROM prospeccao.lead_decisor ld
  LEFT JOIN cnpj.empresa_rural em ON em.cnpj_basico=ld.cnpj_basico
  LEFT JOIN prospeccao.prospect_genetica pg ON pg.cnpj_basico=ld.cnpj_basico
  LEFT JOIN op ON op.cnpj_basico=ld.cnpj_basico
  LEFT JOIN be ON be.cnpj_basico=ld.cnpj_basico
  LEFT JOIN erfb ON erfb.cnpj_basico=ld.cnpj_basico
  LEFT JOIN df ON df.cnpj_basico=ld.cnpj_basico
  LEFT JOIN est ON est.cnpj_basico=ld.cnpj_basico
  LEFT JOIN prospeccao.resto_referencia rr ON rr.cnpj_basico=ld.cnpj_basico
  LEFT JOIN prospeccao.icp527_screen i5 ON i5.cnpj_basico=ld.cnpj_basico
  LEFT JOIN prospeccao.icp_media_screen im ON im.cnpj_basico=ld.cnpj_basico
  LEFT JOIN prospeccao.canal_grupo cg ON cg.cnpj_basico=ld.cnpj_basico
  LEFT JOIN prospeccao.whatsapp_rfb wr ON wr.cnpj_basico=ld.cnpj_basico
  LEFT JOIN prospeccao.canal_tecnico ct ON ct.cnpj_basico=ld.cnpj_basico),
wa_share AS (  -- nº de donos distintos por número (4+ = genérico/contador)
  SELECT wa_raw, count(DISTINCT dono_norm) nd FROM base WHERE wa_raw IS NOT NULL GROUP BY wa_raw)
SELECT
  b.prioridade, b.nome_fazenda, b.razao, b.cnpj_completo, b.uf, b.municipio,
  b.decisor_top AS decisor, b.operador_jovem, b.n_decisores,
  count(*) OVER (PARTITION BY COALESCE(b.dono_norm, b.cnpj_basico)) AS dono_n_fazendas,
  b.capital_mi, b.sinal_genetico, b.touros_nelore,
  CASE WHEN ws.nd>=4 THEN NULL ELSE b.wa_raw END AS whatsapp,   -- guarda: nula número compartilhado
  CASE WHEN ws.nd>=4 THEN NULL ELSE b.whats_alta_conf END AS whats_alta_conf,
  b.celular, b.instagram, b.followers, NULL::text AS porte_digital,
  b.email, b.email_tier, b.telefone_rfb, b.dominio, b.linkedin,
  CASE
    WHEN b.whats_alta_conf AND COALESCE(ws.nd,0)<4 THEN 'WhatsApp'
    WHEN b.email_tier='valid' THEN 'E-mail'
    WHEN b.wa_raw IS NOT NULL AND COALESCE(ws.nd,0)<4 THEN 'WhatsApp'
    WHEN b.email_tier='rfb' THEN 'E-mail (Receita)'
    WHEN b.instagram IS NOT NULL THEN 'Instagram DM'
    WHEN b.email_tier='catch-all' THEN 'E-mail (risco bounce)'
    WHEN b.email_tier='rfb-contador' THEN 'E-mail (contador)'
    WHEN b.tem_tecnico THEN 'Via técnico'
    WHEN b.telefone_rfb IS NOT NULL THEN 'Ligacao (capturar zap)'
    ELSE 'sem canal' END AS canal_recomendado,
  b.cnpj_basico
FROM base b LEFT JOIN wa_share ws ON ws.wa_raw=b.wa_raw;

CREATE INDEX ON prospeccao.fazenda_nacional (prioridade, touros_nelore DESC);
CREATE INDEX ON prospeccao.fazenda_nacional (uf);
CREATE INDEX ON prospeccao.fazenda_nacional (canal_recomendado);
GRANT SELECT ON prospeccao.fazenda_nacional TO wins_app;
SELECT count(*) total, count(DISTINCT cnpj_basico) unicos,
  count(*) FILTER (WHERE whatsapp IS NOT NULL) com_whats,
  count(*) FILTER (WHERE canal_recomendado<>'sem canal') com_canal FROM prospeccao.fazenda_nacional;
