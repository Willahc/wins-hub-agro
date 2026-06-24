-- build_prospect_top3_uf.sql
-- Top 3 prospects por UF com WhatsApp verificado e maior fit com o WiNS Hub Agro.
-- Score calculado AQUI (no banco), a partir da MV prospeccao.lead_demanda.
-- Idempotente: DROP + CREATE da tabela materializada prospeccao.prospect_top3_uf.

DROP TABLE IF EXISTS prospeccao.prospect_top3_uf;

CREATE TABLE prospeccao.prospect_top3_uf AS
WITH base AS (
  SELECT
    ld.uf,
    ld.municipio,
    ld.nome_fazenda,
    ld.razao,
    ld.cnpj_completo,
    ld.cnpj_basico,
    ld.decisor,
    ld.operador_jovem,
    ld.whatsapp,
    ld.whats_alta_conf,
    ld.instagram,
    ld.followers,
    ld.capital_mi,
    ld.sinal_genetico,
    ld.touros_nelore,
    ld.matrizes_municipio,
    ld.deserto_vet,
    ld.tem_canal,
    he.email_decisor AS email_hunter,
    he.verif_status AS email_verif,
    -- ====== SCORE DE FIT (0-100), pesos na ordem do brief ======
    LEAST(100, (
        -- (2) sinal genetico — maior peso entre os criterios pontuados
        CASE ld.sinal_genetico
            WHEN 'alta'  THEN 30
            WHEN 'media' THEN 17
            WHEN 'baixa' THEN 7
            ELSE 0
        END
        -- (3)+(4) capital social / porte (porte_digital esta vazio -> capital como proxy)
        + CASE
            WHEN ld.capital_mi >= 10 THEN 24
            WHEN ld.capital_mi >= 5  THEN 19
            WHEN ld.capital_mi >= 2  THEN 14
            WHEN ld.capital_mi >= 1  THEN 9
            WHEN ld.capital_mi >  0  THEN 3
            ELSE 0
        END
        -- (5) decisor / operador identificado nominalmente
        + CASE WHEN ld.decisor IS NOT NULL AND ld.decisor <> '' THEN 9 ELSE 0 END
        + CASE WHEN ld.operador_jovem IS NOT NULL AND ld.operador_jovem <> '' THEN 6 ELSE 0 END
        -- (6) deserto vet (maior propensao a comprar servico externo)
        + CASE WHEN ld.deserto_vet THEN 10 ELSE 0 END
        -- (7) presenca digital (Instagram) + audiencia
        + CASE WHEN ld.instagram IS NOT NULL AND ld.instagram <> '' THEN 8 ELSE 0 END
        + CASE WHEN ld.followers >= 10000 THEN 4 ELSE 0 END
        -- bonus: WhatsApp em alta confianca (verificado com mais certeza)
        + CASE WHEN ld.whats_alta_conf IS TRUE THEN 8
               WHEN ld.whats_alta_conf IS FALSE THEN 2
               ELSE 0 END
    ))::int AS score_fit
  FROM prospeccao.lead_demanda ld
  LEFT JOIN prospeccao.hunter_email he ON he.cnpj_basico = ld.cnpj_basico
  -- FILTRO DURO: so entra WhatsApp de ALTA CONFIANCA (verificado: DDD bate a UF,
  -- origem Serper/marca/IG/site). ANTES exigia so 'whatsapp <> ''', o que deixava
  -- entrar os numeros INFERIDOS do telefone declarado na Receita (contador/3os/
  -- numero velho) = "pessoas avulsas / outros negocios". Todas as 12 UFs tem >=4
  -- leads alta-conf, entao o Top 3 continua cheio. (jun/24)
  WHERE ld.whats_alta_conf IS TRUE
    -- exclui número compartilhado por >=3 decisores distintos (central/contador):
    -- mesmo alta-conf, não é o contato confiável daquele lead específico.
    AND regexp_replace(ld.whatsapp,'\D','','g') NOT IN (SELECT fone FROM prospeccao.contato_compartilhado)
    AND ld.uf IN ('MS','GO','MT','TO','PA','BA','MG','RO','MA','PI','PR','SP')
),
ranked AS (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY uf
      ORDER BY score_fit DESC,
               (whats_alta_conf IS TRUE) DESC,
               capital_mi DESC NULLS LAST,
               followers DESC NULLS LAST,
               matrizes_municipio DESC NULLS LAST,
               cnpj_completo
    ) AS rn
  FROM base
)
SELECT uf, rn AS rank_uf, municipio, nome_fazenda, razao, cnpj_completo, cnpj_basico,
       decisor, operador_jovem, whatsapp, whats_alta_conf, email_hunter, email_verif, instagram, followers,
       capital_mi, sinal_genetico, touros_nelore, matrizes_municipio, deserto_vet, tem_canal,
       score_fit
FROM ranked
WHERE rn <= 3
ORDER BY uf, rn;

SELECT uf, count(*) AS n, min(score_fit) AS min_score, max(score_fit) AS max_score
FROM prospeccao.prospect_top3_uf GROUP BY uf ORDER BY uf;
