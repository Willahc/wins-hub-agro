-- Materializa o ALVO da última fronteira Hunter (jun/13, fechamento do enriquecimento).
-- Descoberta: a fronteira IN-ICP (estados de pecuária Nelore) está ESGOTADA — 0 fazendas
-- nomeáveis com domínio próprio limpo ainda não rodadas. Só sobram:
--   (A) cabanha_extra com domínio limpo (39) — IN-ICP, vale rodar.
--   (B) cap>=R$5M FORA dos estados de pecuária (SP/PR/RS/ES/SC...) — FORA do ICP Nelore-elite,
--       opt-in do dono (geografia taurina/leiteira/grão; baixa aderência ao sêmen Nelore).
-- O runner (hunter_finder_frontier.py) lê desta tabela; default = só fonte LIKE '%icp%'.
DROP TABLE IF EXISTS prospeccao.hunter_frontier_todo;
CREATE TABLE prospeccao.hunter_frontier_todo AS
WITH op AS (
  SELECT DISTINCT ON (cnpj_basico) cnpj_basico, nome
  FROM prospeccao.contato_candidatos WHERE faixa BETWEEN 3 AND 5
  ORDER BY cnpj_basico, score_alcancavel DESC, faixa
),
-- (A) cabanha_extra com domínio próprio limpo, não rodada
ce AS (
  SELECT DISTINCT ON (cb) cb, decisor FROM (
    SELECT left(regexp_replace(cnpj14,'[^0-9]','','g'),8) cb, decisor, touros_nelore
    FROM prospeccao.cabanha_extra
    WHERE length(regexp_replace(coalesce(cnpj14,''),'[^0-9]','','g'))=14
  ) z ORDER BY cb, touros_nelore DESC NULLS LAST
),
frontier_a AS (
  SELECT e.cnpj_basico,
         COALESCE(NULLIF(ce.decisor,''), ld.decisor_top) AS nome,
         false AS eh_operador,
         lower(split_part(e.correio_eletronico,'@',2)) AS dominio,
         ld.uf, round(em.capital_social/1e6,1) AS capital_mi,
         CASE pg.confianca WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baixa' THEN 3 ELSE 9 END AS pri,
         'cabanha_extra_icp'::text AS fonte
  FROM ce
  JOIN cnpj.estabelecimento_rural e ON e.cnpj_basico=ce.cb
  LEFT JOIN prospeccao.lead_decisor ld ON ld.cnpj_basico=ce.cb
  LEFT JOIN cnpj.empresa_rural em ON em.cnpj_basico=ce.cb
  LEFT JOIN prospeccao.prospect_genetica pg ON pg.cnpj_basico=ce.cb
  WHERE e.correio_eletronico ~ '@'
),
-- (B) fora dos estados de pecuária, cap>=5M, nomeável (opt-in)
frontier_b AS (
  SELECT ld.cnpj_basico,
         COALESCE(op.nome, ld.decisor_top) AS nome,
         (op.nome IS NOT NULL) AS eh_operador,
         lower(split_part(e.correio_eletronico,'@',2)) AS dominio,
         ld.uf, round(em.capital_social/1e6,1) AS capital_mi,
         CASE pg.confianca WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baixa' THEN 3 ELSE 9 END AS pri,
         'fora_icp_cap5m'::text AS fonte
  FROM prospeccao.lead_decisor ld
  JOIN cnpj.estabelecimento_rural e ON e.cnpj_basico=ld.cnpj_basico
  JOIN cnpj.empresa_rural em ON em.cnpj_basico=ld.cnpj_basico
  LEFT JOIN op ON op.cnpj_basico=ld.cnpj_basico
  LEFT JOIN prospeccao.prospect_genetica pg ON pg.cnpj_basico=ld.cnpj_basico
  WHERE ld.uf NOT IN ('MT','MS','GO','PA','TO','MG','BA','RO')
    AND e.correio_eletronico ~ '@'
    AND em.capital_social >= 5000000 AND em.capital_social < 150000000  -- exclui conglomerado
)
SELECT DISTINCT ON (cnpj_basico) * FROM (
  SELECT * FROM frontier_a
  UNION ALL
  SELECT * FROM frontier_b
) u
WHERE dominio<>''
  AND dominio NOT IN ('gmail.com','hotmail.com','outlook.com','yahoo.com.br','yahoo.com','live.com','bol.com.br','terra.com.br','uol.com.br','icloud.com')
  AND dominio !~ '(contab|assessor|advoc|advog|portaldbo|ancp|geneplus|selectsires|semex|serasa|\.gov|\.org\.br|\.mil)'
  AND nome ~ '\S\s+\S'                                              -- Hunter precisa first+last
  AND cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_email)
  AND cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_operador)
ORDER BY cnpj_basico, fonte;   -- cabanha_extra_icp ganha de fora_icp_cap5m no dedup

ALTER TABLE prospeccao.hunter_frontier_todo ADD PRIMARY KEY (cnpj_basico);
SELECT fonte, count(*), count(*) FILTER (WHERE pri<9) com_sinal_genetico FROM prospeccao.hunter_frontier_todo GROUP BY 1 ORDER BY 1;
