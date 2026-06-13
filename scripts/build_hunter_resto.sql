-- "O RESTO" dos operadores jovens (jun/13). Os 5.847 candidatos (contato_candidatos faixa 3-5)
-- ainda NÃO rodados no Hunter NÃO têm domínio próprio limpo no RFB (4.064 usam gmail, ~1.228 sem
-- e-mail, ~555 só domínio de contador/advogado, 0 domínio próprio). O método de ontem (domínio+nome)
-- está ESGOTADO p/ eles. Única via restante: Hunter email-finder com `company` (razão social) em vez
-- de `domain` — o Hunter tenta resolver o domínio da empresa sozinho. Hit-rate DESCONHECIDO/baixo p/
-- fazenda de gmail (mesma parede estrutural do WhatsApp), mas vale testar nas de melhor sinal ICP.
-- Prioriza por sinal genético (alta>media>baixa) e capital. Runner: hunter_finder_resto.py.
DROP TABLE IF EXISTS prospeccao.hunter_resto_todo;
CREATE TABLE prospeccao.hunter_resto_todo AS
WITH cc AS (
  SELECT DISTINCT ON (cnpj_basico) cnpj_basico, nome, faixa
  FROM prospeccao.contato_candidatos WHERE faixa BETWEEN 3 AND 5
  ORDER BY cnpj_basico, score_alcancavel DESC, faixa
)
SELECT cc.cnpj_basico,
       cc.nome                                            AS operador,
       cc.faixa,
       ld.razao,
       -- nome de empresa p/ o Hunter resolver (só tira o sufixo societário no fim; mantém Fazenda/Agropecuaria)
       initcap(regexp_replace(ld.razao,
         '\s+(LTDA|S/?A|S\.?A\.?|EIRELI|ME|EPP)\.?\s*$','','i')) AS company_hint,
       ld.uf, ld.municipio,
       COALESCE(pg.confianca,'(sem sinal)')               AS sinal,
       round(em.capital_social/1e6,1)                     AS capital_mi,
       CASE pg.confianca WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baixa' THEN 3
            WHEN 'descartar' THEN 4 ELSE 5 END            AS pri
FROM cc
JOIN prospeccao.lead_decisor ld ON ld.cnpj_basico=cc.cnpj_basico
LEFT JOIN cnpj.empresa_rural em ON em.cnpj_basico=cc.cnpj_basico
LEFT JOIN prospeccao.prospect_genetica pg ON pg.cnpj_basico=cc.cnpj_basico
WHERE cc.cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_email)
  AND cc.cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_operador)
  AND cc.nome ~ '\S\s+\S'                                 -- Hunter precisa first+last
  AND ld.razao IS NOT NULL AND ld.razao<>'';

ALTER TABLE prospeccao.hunter_resto_todo ADD PRIMARY KEY (cnpj_basico);
SELECT sinal, count(*), count(*) FILTER (WHERE capital_mi>=5) cap5m FROM prospeccao.hunter_resto_todo GROUP BY 1 ORDER BY min(pri);
