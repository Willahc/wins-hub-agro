-- LIGAR O CANO (jun/14): dobra prospeccao.fazenda_cel.whatsapp_cel no campo wa_raw
-- da matview fazenda_nacional. Recupera ~17,3k celulares WhatsApp-able (DDD+tel do RFB,
-- ja com 9o digito via cel_whats) que o KPI ja contava mas a coluna de Contato nao mostrava.
-- Matview exige DROP+CREATE; feito em transacao atomica + recria 3 indices + grant wins_app.
-- Idempotente: reexecutar regenera a matview a partir da definicao corrente (que ja tem o fc).

BEGIN;
DROP MATERIALIZED VIEW prospeccao.fazenda_nacional;
CREATE MATERIALIZED VIEW prospeccao.fazenda_nacional AS
 WITH est AS (
         SELECT DISTINCT ON (estabelecimento_rural.cnpj_basico) estabelecimento_rural.cnpj_basico,
            NULLIF(estabelecimento_rural.nome_fantasia, ''::text) AS nome_fazenda,
            (((((((substr(lpad(estabelecimento_rural.cnpj_basico::text, 8, '0'::text), 1, 2) || '.'::text) || substr(lpad(estabelecimento_rural.cnpj_basico::text, 8, '0'::text), 3, 3)) || '.'::text) || substr(lpad(estabelecimento_rural.cnpj_basico::text, 8, '0'::text), 6, 3)) || '/'::text) || lpad(estabelecimento_rural.cnpj_ordem::text, 4, '0'::text)) || '-'::text) || lpad(estabelecimento_rural.cnpj_dv::text, 2, '0'::text) AS cnpj_completo,
            NULLIF(estabelecimento_rural.ddd_1::text, ''::text) || NULLIF(estabelecimento_rural.telefone_1::text, ''::text) AS telefone_rfb
           FROM cnpj.estabelecimento_rural
          ORDER BY estabelecimento_rural.cnpj_basico, (estabelecimento_rural.identificador_matriz_filial::text = '1'::text) DESC, (COALESCE(estabelecimento_rural.telefone_1, ''::character varying)::text <> ''::text) DESC, estabelecimento_rural.cnpj_ordem
        ), op AS (
         SELECT DISTINCT ON (contato_candidatos.cnpj_basico) contato_candidatos.cnpj_basico,
            contato_candidatos.nome
           FROM prospeccao.contato_candidatos
          WHERE contato_candidatos.faixa >= 3 AND contato_candidatos.faixa <= 5
          ORDER BY contato_candidatos.cnpj_basico, contato_candidatos.score_alcancavel DESC, contato_candidatos.faixa
        ), be AS (
         SELECT DISTINCT ON (hunter_entrega.cnpj_basico) hunter_entrega.cnpj_basico,
            hunter_entrega.email,
                CASE
                    WHEN hunter_entrega.tier_entrega = 'A-confirmada'::text THEN 'valid'::text
                    WHEN hunter_entrega.tier_entrega = 'B-catchall'::text THEN 'catch-all'::text
                    ELSE NULL::text
                END AS email_tier
           FROM prospeccao.hunter_entrega
          WHERE hunter_entrega.tier_entrega = ANY (ARRAY['A-confirmada'::text, 'B-catchall'::text])
          ORDER BY hunter_entrega.cnpj_basico, (
                CASE hunter_entrega.tier_entrega
                    WHEN 'A-confirmada'::text THEN 1
                    ELSE 2
                END)
        ), erfb AS (
         SELECT DISTINCT ON (estabelecimento_rural.cnpj_basico) estabelecimento_rural.cnpj_basico,
            lower(btrim(estabelecimento_rural.correio_eletronico)) AS email_rfb,
                CASE
                    WHEN estabelecimento_rural.correio_eletronico ~* 'cont(abil|ador|abilidade)|escritorio|assessoria|fiscal|@.*contab'::text THEN 'rfb-contador'::text
                    ELSE 'rfb'::text
                END AS email_rfb_tier
           FROM cnpj.estabelecimento_rural
          WHERE estabelecimento_rural.correio_eletronico ~* '^[^@ ]+@[^@ ]+\.[^@ ]+$'::text
          ORDER BY estabelecimento_rural.cnpj_basico, (estabelecimento_rural.identificador_matriz_filial::text = '1'::text) DESC, estabelecimento_rural.cnpj_ordem
        ), df AS (
         SELECT decisores_fazenda.cnpj_basico,
            decisores_fazenda.n_decisores,
            decisores_fazenda.socio_jovem
           FROM prospeccao.decisores_fazenda
        ), base AS (
         SELECT ld.cnpj_basico,
            ld.uf,
            ld.municipio,
            ld.decisor_top,
            ld.razao,
            ld.linkedin,
            lower(btrim(regexp_replace(ld.decisor_top, '\s*\(.*$'::text, ''::text))) AS dono_norm,
            COALESCE(est.nome_fazenda, ld.razao) AS nome_fazenda,
            est.cnpj_completo,
            est.telefone_rfb,
            COALESCE(op.nome, df.socio_jovem) AS operador_jovem,
            COALESCE(df.n_decisores, 1::bigint) AS n_decisores,
            round(em.capital_social / '1000000'::numeric, 1) AS capital_mi,
            COALESCE(pg.confianca, '-'::text) AS sinal_genetico,
                CASE pg.confianca
                    WHEN 'alta'::text THEN 1
                    WHEN 'media'::text THEN 2
                    WHEN 'baixa'::text THEN 3
                    WHEN 'descartar'::text THEN 4
                    ELSE 5
                END AS prioridade,
                CASE
                    WHEN pg.confianca = ANY (ARRAY['alta'::text, 'media'::text, 'baixa'::text]) THEN pg.touros_nelore
                    ELSE 0
                END AS touros_nelore,
            rr.whats_ufmatch AS whats_alta_conf,
            rr.followers,
            COALESCE(rr.whatsapp, rr.whatsapp_bio, i5.whatsapp, i5.cab_whatsapp, im.cab_whatsapp, cg.whatsapp_grupo, wr.whatsapp, fc.whatsapp_cel) AS wa_raw,
            COALESCE(i5.celular, i5.cab_cel, im.cab_cel) AS celular,
            COALESCE(rr.instagram, i5.instagram, i5.cab_instagram, im.cab_instagram, cg.instagram_grupo) AS instagram,
            COALESCE(be.email, erfb.email_rfb) AS email,
            COALESCE(be.email_tier, erfb.email_rfb_tier) AS email_tier,
            rr.dominio_cand AS dominio,
            ct.cnpj_basico IS NOT NULL AS tem_tecnico
           FROM prospeccao.lead_decisor ld
             LEFT JOIN cnpj.empresa_rural em ON em.cnpj_basico::text = ld.cnpj_basico::text
             LEFT JOIN prospeccao.prospect_genetica pg ON pg.cnpj_basico::text = ld.cnpj_basico::text
             LEFT JOIN op ON op.cnpj_basico::text = ld.cnpj_basico::text
             LEFT JOIN be ON be.cnpj_basico::text = ld.cnpj_basico::text
             LEFT JOIN erfb ON erfb.cnpj_basico::text = ld.cnpj_basico::text
             LEFT JOIN df ON df.cnpj_basico::text = ld.cnpj_basico::text
             LEFT JOIN est ON est.cnpj_basico::text = ld.cnpj_basico::text
             LEFT JOIN prospeccao.resto_referencia rr ON rr.cnpj_basico::text = ld.cnpj_basico::text
             LEFT JOIN prospeccao.icp527_screen i5 ON i5.cnpj_basico::text = ld.cnpj_basico::text
             LEFT JOIN prospeccao.icp_media_screen im ON im.cnpj_basico::text = ld.cnpj_basico::text
             LEFT JOIN prospeccao.canal_grupo cg ON cg.cnpj_basico::text = ld.cnpj_basico::text
             LEFT JOIN prospeccao.whatsapp_rfb wr ON wr.cnpj_basico::text = ld.cnpj_basico::text
             LEFT JOIN prospeccao.canal_tecnico ct ON ct.cnpj_basico::text = ld.cnpj_basico::text
             LEFT JOIN prospeccao.fazenda_cel fc ON fc.cnpj_basico::text = ld.cnpj_basico::text
        ), wa_share AS (
         SELECT base.wa_raw,
            count(DISTINCT base.dono_norm) AS nd
           FROM base
          WHERE base.wa_raw IS NOT NULL
          GROUP BY base.wa_raw
        )
 SELECT b.prioridade,
    b.nome_fazenda,
    b.razao,
    b.cnpj_completo,
    b.uf,
    b.municipio,
    b.decisor_top AS decisor,
    b.operador_jovem,
    b.n_decisores,
    count(*) OVER (PARTITION BY (COALESCE(b.dono_norm, b.cnpj_basico::text))) AS dono_n_fazendas,
    b.capital_mi,
    b.sinal_genetico,
    b.touros_nelore,
        CASE
            WHEN ws.nd >= 4 THEN NULL::text
            ELSE b.wa_raw
        END AS whatsapp,
        CASE
            WHEN ws.nd >= 4 THEN NULL::boolean
            ELSE b.whats_alta_conf
        END AS whats_alta_conf,
    b.celular,
    b.instagram,
    b.followers,
    NULL::text AS porte_digital,
    b.email,
    b.email_tier,
    b.telefone_rfb,
    b.dominio,
    b.linkedin,
        CASE
            WHEN b.whats_alta_conf AND COALESCE(ws.nd, 0::bigint) < 4 THEN 'WhatsApp'::text
            WHEN b.email_tier = 'valid'::text THEN 'E-mail'::text
            WHEN b.wa_raw IS NOT NULL AND COALESCE(ws.nd, 0::bigint) < 4 THEN 'WhatsApp'::text
            WHEN b.email_tier = 'rfb'::text THEN 'E-mail (Receita)'::text
            WHEN b.instagram IS NOT NULL THEN 'Instagram DM'::text
            WHEN b.email_tier = 'catch-all'::text THEN 'E-mail (risco bounce)'::text
            WHEN b.email_tier = 'rfb-contador'::text THEN 'E-mail (contador)'::text
            WHEN b.tem_tecnico THEN 'Via técnico'::text
            WHEN b.telefone_rfb IS NOT NULL THEN 'Ligacao (capturar zap)'::text
            ELSE 'sem canal'::text
        END AS canal_recomendado,
    b.cnpj_basico
   FROM base b
     LEFT JOIN wa_share ws ON ws.wa_raw = b.wa_raw;
;
CREATE INDEX fazenda_nacional_prioridade_touros_nelore_idx ON prospeccao.fazenda_nacional USING btree (prioridade, touros_nelore DESC);
CREATE INDEX fazenda_nacional_uf_idx ON prospeccao.fazenda_nacional USING btree (uf);
CREATE INDEX fazenda_nacional_canal_recomendado_idx ON prospeccao.fazenda_nacional USING btree (canal_recomendado);
GRANT SELECT, INSERT, UPDATE, DELETE ON prospeccao.fazenda_nacional TO wins_app;
COMMIT;
