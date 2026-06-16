-- Tabela de apresentação dos leads holding (ponto cego) para o front end.
-- Consolida: cadastro (cnpj_rural) + tipo/decisor (lead_decisor) + âncora agro
-- (holding_blind_spot) + MELHOR CANAL já no banco (WhatsApp confirmado direto/via âncora, e-mail).
-- Snapshot estático (dados batch). Re-rodar este arquivo regenera. Idempotente.
\pset pager off

-- universo de WhatsApp CONFIRMADO por cnpj_basico (raspagem/zap; exclui whatsapp_rfb reconstruído)
DROP TABLE IF EXISTS prospeccao._wa_conf;
CREATE TABLE prospeccao._wa_conf AS
SELECT cnpj_basico, (array_agg(w))[1] AS whats FROM (
    SELECT cnpj_basico, regexp_replace(coalesce(whatsapp_cel,''),'\D','','g') w FROM prospeccao.fazenda_cel
    UNION ALL SELECT cnpj_basico, regexp_replace(coalesce(whatsapp,''),'\D','','g') FROM prospeccao.candidato_zap
    UNION ALL SELECT cnpj_basico, regexp_replace(coalesce(tec_whatsapp,''),'\D','','g') FROM prospeccao.candidato_tecnico
    UNION ALL SELECT cnpj_basico, regexp_replace(coalesce(whatsapp,''),'\D','','g') FROM prospeccao.icp527_screen
    UNION ALL SELECT cnpj_basico, regexp_replace(coalesce(cab_whatsapp,''),'\D','','g') FROM prospeccao.icp_media_screen
    UNION ALL SELECT cnpj_basico, regexp_replace(coalesce(whatsapp,''),'\D','','g') FROM prospeccao.resto_referencia
    UNION ALL SELECT cnpj_basico, regexp_replace(coalesce(whatsapp,''),'\D','','g') FROM prospeccao.site_contato
    UNION ALL SELECT cnpj_basico, regexp_replace(coalesce(whatsapp,''),'\D','','g') FROM prospeccao.tecnico_social
    UNION ALL SELECT cnpj_basico, regexp_replace(coalesce(whatsapp,''),'\D','','g') FROM prospeccao.top500_scrape
    UNION ALL SELECT cnpj_basico, regexp_replace(coalesce(whatsapp,''),'\D','','g') FROM prospeccao.top500_social
    UNION ALL SELECT cnpj_basico, regexp_replace(coalesce(whatsapp,''),'\D','','g') FROM prospeccao.vet_pecuaria
    UNION ALL SELECT cnpj_basico, regexp_replace(coalesce(whatsapp_cel,''),'\D','','g') FROM prospeccao.fazenda_expansao
  ) s WHERE length(w)>=10 GROUP BY cnpj_basico;
CREATE INDEX ON prospeccao._wa_conf(cnpj_basico);

DROP TABLE IF EXISTS prospeccao.holding_lead_ui;
CREATE TABLE prospeccao.holding_lead_ui AS
SELECT
  l.cnpj14, l.cnpj_basico, l.razao, l.tipo, l.uf, l.municipio,
  cr.nome_fantasia, cr.cnae_principal, cr.capital_social, cr.situacao, cr.email,
  b.agro_cnpj_basico, b.n_socios_agro, b.nome_socio_comum,
  er.razao_social AS ancora_razao,
  -- melhor WhatsApp: direto do holding > via fazenda âncora
  COALESCE(wd.whats, wa.whats) AS whatsapp,
  CASE WHEN wd.whats IS NOT NULL THEN 'direto'
       WHEN wa.whats IS NOT NULL THEN 'ancora' ELSE NULL END AS whats_origem,
  -- canal recomendado
  CASE WHEN COALESCE(wd.whats, wa.whats) IS NOT NULL THEN 'whatsapp'
       WHEN cr.email IS NOT NULL AND cr.email<>'' THEN 'email'
       ELSE 'sem' END AS canal,
  -- score simples p/ ordenar: WhatsApp(+40) > email(+15); + vínculo societário; + capital tier
  ( CASE WHEN COALESCE(wd.whats, wa.whats) IS NOT NULL THEN 40
         WHEN cr.email IS NOT NULL AND cr.email<>'' THEN 15 ELSE 0 END
    + LEAST(COALESCE(b.n_socios_agro,0),6)*8
    + CASE WHEN cr.capital_social>=1000000 THEN 10 WHEN cr.capital_social>=100000 THEN 5 ELSE 0 END
  ) AS score
FROM prospeccao.lead_decisor l
LEFT JOIN prospeccao.cnpj_rural cr ON cr.cnpj = l.cnpj14
LEFT JOIN prospeccao.holding_blind_spot b ON b.cnpj_basico = l.cnpj_basico
LEFT JOIN cnpj.empresa_rural er ON er.cnpj_basico = b.agro_cnpj_basico
LEFT JOIN prospeccao._wa_conf wd ON wd.cnpj_basico = l.cnpj_basico
LEFT JOIN prospeccao._wa_conf wa ON wa.cnpj_basico = b.agro_cnpj_basico
WHERE l.tipo LIKE 'HOLDING/%';

CREATE INDEX ON prospeccao.holding_lead_ui(uf);
CREATE INDEX ON prospeccao.holding_lead_ui(canal);
CREATE INDEX ON prospeccao.holding_lead_ui(score DESC);
DROP TABLE prospeccao._wa_conf;

\echo '=== holding_lead_ui criada ==='
SELECT count(*) total,
       count(*) FILTER (WHERE canal='whatsapp') com_whats,
       count(*) FILTER (WHERE canal='email') so_email,
       count(*) FILTER (WHERE canal='sem') sem_canal
FROM prospeccao.holding_lead_ui;
