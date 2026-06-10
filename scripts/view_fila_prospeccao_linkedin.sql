-- Adiciona linkedin (de lead_decisor) à v_fila_prospeccao p/ entrar no score de contato.
-- Coluna anexada NO FIM (após 'ativo') → CREATE OR REPLACE seguro (mantém colunas/ordem).
CREATE OR REPLACE VIEW prospeccao.v_fila_prospeccao AS
 WITH icp AS (
         SELECT 'ALTA'::text AS tier, s.cnpj_basico, g.match_fazenda AS cab, s.razao, s.decisor,
            s.uf, s.municipio, s.touros_nelore AS nel, s.email, s.email_status, s.telefone,
            s.cab_instagram AS ig, s.cab_cel, s.cab_cel_conf, s.validade
           FROM prospeccao.icp527_screen s
             JOIN prospeccao.prospect_genetica g ON g.cnpj_basico::text = s.cnpj_basico::text
        UNION ALL
         SELECT 'MEDIA'::text, icp_media_screen.cnpj_basico, icp_media_screen.cabanha,
            icp_media_screen.razao, icp_media_screen.decisor, icp_media_screen.uf,
            icp_media_screen.municipio, icp_media_screen.touros_nelore, icp_media_screen.email,
            icp_media_screen.email_status, icp_media_screen.telefone, icp_media_screen.cab_instagram,
            icp_media_screen.cab_cel, icp_media_screen.cab_cel_conf, icp_media_screen.validade
           FROM prospeccao.icp_media_screen
        )
 SELECT i.tier, i.cnpj_basico AS cnpj, i.cab AS cabanha, i.razao AS fazenda, i.decisor, i.uf,
    i.municipio, i.nel AS nelore,
    COALESCE(h.email_decisor, ig.email,
        CASE WHEN i.email_status = ANY (ARRAY['mx_ok'::text, 'free_entregavel'::text]) THEN i.email ELSE NULL::text END) AS email,
        CASE WHEN h.email_decisor IS NOT NULL THEN 'decisor'::text
             WHEN ig.email IS NOT NULL THEN 'fazenda'::text
             WHEN i.email_status = ANY (ARRAY['mx_ok'::text, 'free_entregavel'::text]) THEN 'receita'::text
             ELSE NULL::text END AS email_origem,
    COALESCE(ig.whatsapp, CASE WHEN i.cab_cel_conf = 'alta(DDD)'::text THEN i.cab_cel ELSE NULL::text END) AS whatsapp,
    (('('::text || "left"(i.telefone, 2)) || ') '::text) || substr(i.telefone, 3) AS telefone,
    i.ig AS instagram,
    i.validade ~~* '%ATIVA%'::text AS ativo,
    ld.linkedin AS linkedin
   FROM icp i
     LEFT JOIN prospeccao.hunter_email h ON h.cnpj_basico::text = i.cnpj_basico::text
     LEFT JOIN prospeccao.ig_contato ig ON ig.username = i.ig
     LEFT JOIN prospeccao.lead_decisor ld ON ld.cnpj_basico::text = i.cnpj_basico::text;
