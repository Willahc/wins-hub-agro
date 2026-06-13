-- Consolida + tiering da entrega Hunter (decisor + operador) p/ a fila Monte Sião.
-- Fecha o enriquecimento (jun/13): une hunter_email + hunter_operador, classifica caixa
-- (A=valid / B=catch-all), origem (domínio próprio vs empresa do dono), e FLAGA conglomerado
-- (capital>=R$150M, regra do ICP-fix) p/ não enganar a Monte Sião com J&F/Bom Futuro/holdings.
-- Idempotente: CREATE OR REPLACE.
CREATE OR REPLACE VIEW prospeccao.hunter_entrega AS
WITH bruto AS (
    -- e-mails do run principal (hunter_email): sempre domínio próprio do RFB
    SELECT he.cnpj_basico,
           CASE WHEN he.status='achado_op' THEN 'operador' ELSE 'decisor' END AS papel,
           he.decisor               AS contato,
           he.email_decisor         AS email,
           he.dominio,
           'dominio_proprio'        AS origem,
           he.score,
           he.verif_status
    FROM prospeccao.hunter_email he
    WHERE he.email_decisor IS NOT NULL AND he.email_decisor <> ''
  UNION
    -- e-mails do run do operador jovem (hunter_operador): farm = domínio próprio,
    -- outra_empresa = mailbox do dono na empresa DELE (sinal de patrimônio, não lixo)
    SELECT ho.cnpj_basico,
           'operador'               AS papel,
           ho.operador              AS contato,
           ho.email_operador        AS email,
           ho.dominio,
           CASE WHEN ho.status='achado_farm' THEN 'dominio_proprio'
                ELSE 'empresa_do_dono' END AS origem,
           ho.score,
           ho.verif_status
    FROM prospeccao.hunter_operador ho
    WHERE ho.email_operador IS NOT NULL AND ho.email_operador <> ''
  UNION
    -- e-mails do "resto" (operador em domínio que o Serper resolveu, não o RFB) — qualidade menor,
    -- origem marcada p/ a Mari saber; exclui os reprovados na verificação (invalid)
    SELECT hr.cnpj_basico,
           'operador'               AS papel,
           hr.operador              AS contato,
           hr.email_operador        AS email,
           hr.dominio_resolvido     AS dominio,
           'dominio_serper'         AS origem,
           hr.score,
           hr.verif_status
    FROM prospeccao.hunter_resto hr
    WHERE hr.email_operador IS NOT NULL AND hr.email_operador <> ''
      AND COALESCE(hr.verif_status,'') <> 'invalid'
  UNION
    -- e-mail RASPADO do site próprio da fazenda (scrape_sites) — publicado por eles, Hunter-verificado
    SELECT sc.cnpj_basico,
           'fazenda'                AS papel,
           NULL                     AS contato,
           split_part(sc.emails,',',1) AS email,
           sc.dominio,
           'site_scrape'            AS origem,
           NULL::int                AS score,
           sc.verif_status
    FROM prospeccao.site_contato sc
    WHERE sc.emails IS NOT NULL AND sc.emails <> ''
      AND sc.verif_status IN ('valid','accept_all')
)
SELECT DISTINCT ON (b.cnpj_basico, lower(b.email))
       b.cnpj_basico,
       ld.razao,
       ld.uf,
       ld.municipio,
       b.papel,
       b.contato,
       lower(b.email)                                   AS email,
       b.dominio,
       b.origem,
       b.verif_status,
       (em.capital_social >= 150000000)                 AS conglomerado,
       round(em.capital_social/1e6, 1)                  AS capital_mi,
       COALESCE(pg.touros_nelore, 0)                     AS touros_nelore,
       COALESCE(pg.confianca, '-')                       AS sinal_genetico,
       ld.decisor_top,
       ld.linkedin,
       CASE
           WHEN em.capital_social >= 150000000          THEN 'X-conglomerado'
           WHEN b.verif_status = 'valid'                THEN 'A-confirmada'
           WHEN b.verif_status = 'accept_all'           THEN 'B-catchall'
           ELSE 'C-revisar'
       END                                              AS tier_entrega
FROM bruto b
LEFT JOIN prospeccao.lead_decisor ld ON ld.cnpj_basico = b.cnpj_basico
LEFT JOIN cnpj.empresa_rural     em ON em.cnpj_basico = b.cnpj_basico
LEFT JOIN prospeccao.prospect_genetica pg ON pg.cnpj_basico = b.cnpj_basico
WHERE COALESCE(b.verif_status,'') <> 'invalid'   -- exclui caixas reprovadas (Hunter ou SMTP)
ORDER BY b.cnpj_basico, lower(b.email),
         (b.verif_status='valid') DESC;   -- prefere a linha 'valid' se o mesmo e-mail aparecer 2x
