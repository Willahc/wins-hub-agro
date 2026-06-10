CREATE VIEW prospeccao.v_fila_prospeccao AS
 WITH icp AS (
         SELECT 'ALTA'::text AS tier,
            s.cnpj_basico,
            g.match_fazenda AS cab,
            s.razao,
            s.decisor,
            s.uf,
            s.municipio,
            s.touros_nelore AS nel,
            s.email,
            s.email_status,
            s.telefone,
            s.cab_instagram AS ig,
            s.cab_cel,
            s.cab_cel_conf,
            s.validade
           FROM (prospeccao.icp527_screen s
             JOIN prospeccao.prospect_genetica g ON (((g.cnpj_basico)::text = (s.cnpj_basico)::text)))
        UNION ALL
         SELECT 'MEDIA'::text,
            icp_media_screen.cnpj_basico,
            icp_media_screen.cabanha,
            icp_media_screen.razao,
            icp_media_screen.decisor,
            icp_media_screen.uf,
            icp_media_screen.municipio,
            icp_media_screen.touros_nelore,
            icp_media_screen.email,
            icp_media_screen.email_status,
            icp_media_screen.telefone,
            icp_media_screen.cab_instagram,
            icp_media_screen.cab_cel,
            icp_media_screen.cab_cel_conf,
            icp_media_screen.validade
           FROM prospeccao.icp_media_screen
        )
 SELECT i.tier,
    i.cnpj_basico AS cnpj,
    i.cab AS cabanha,
    i.razao AS fazenda,
