-- "O POÇO" (jun/13): fazendas do ICP (pecuária + capital>=R$1M) que AINDA não têm Instagram mapeado
-- em NENHUMA fonte e ainda não passaram pelo harvest. Alvo da perfuração brand->IG->WhatsApp.
-- Injeta direto em hunter_resto_todo (mesmo schema) p/ reusar todo o pipeline (harvest/whats/hunter)
-- sem alterar script. operador = decisor_top (não há candidato jovem mapeado nessas).
INSERT INTO prospeccao.hunter_resto_todo (cnpj_basico, operador, faixa, razao, company_hint, uf, municipio, sinal, capital_mi, pri)
WITH ig_map AS (
  SELECT cnpj_basico FROM prospeccao.resto_referencia WHERE instagram IS NOT NULL AND instagram<>''
  UNION SELECT cnpj_basico FROM prospeccao.top500_social WHERE instagram IS NOT NULL AND instagram<>''
  UNION SELECT cnpj_basico FROM prospeccao.tecnico_social WHERE instagram IS NOT NULL AND instagram<>''
  UNION SELECT cnpj_basico FROM prospeccao.candidato_zap WHERE instagram IS NOT NULL AND instagram<>''
  UNION SELECT cnpj_basico FROM prospeccao.maria_pilot WHERE instagram IS NOT NULL AND instagram<>''
  UNION SELECT cnpj_basico FROM prospeccao.icp527_screen WHERE COALESCE(instagram,cab_instagram)<>''
  UNION SELECT cnpj_basico FROM prospeccao.icp_media_screen WHERE cab_instagram<>''
  UNION SELECT left(regexp_replace(cnpj,'[^0-9]','','g'),8) FROM prospeccao.cabanha_zap WHERE instagram<>'' AND length(regexp_replace(cnpj,'[^0-9]','','g'))>=8
  UNION SELECT left(regexp_replace(cnpj14,'[^0-9]','','g'),8) FROM prospeccao.cabanha_extra WHERE instagram<>'' AND length(regexp_replace(coalesce(cnpj14,''),'[^0-9]','','g'))=14
)
SELECT ld.cnpj_basico,
       ld.decisor_top AS operador,
       NULL::int AS faixa,
       ld.razao,
       initcap(regexp_replace(ld.razao,'\s+(LTDA|S/?A|S\.?A\.?|EIRELI|ME|EPP)\.?\s*$','','i')) AS company_hint,
       ld.uf, ld.municipio,
       COALESCE(pg.confianca,'(sem sinal)') AS sinal,
       round(em.capital_social/1e6,1) AS capital_mi,
       CASE pg.confianca WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baixa' THEN 3 WHEN 'descartar' THEN 4 ELSE 5 END AS pri
FROM prospeccao.lead_decisor ld
JOIN cnpj.empresa_rural em ON em.cnpj_basico=ld.cnpj_basico
LEFT JOIN prospeccao.prospect_genetica pg ON pg.cnpj_basico=ld.cnpj_basico
WHERE ld.uf IN ('MT','MS','GO','PA','TO','MG','BA','RO')
  AND em.capital_social >= 1000000
  AND em.capital_social < 150000000                       -- exclui conglomerado
  AND ld.razao IS NOT NULL AND ld.razao<>''
  AND ld.cnpj_basico NOT IN (SELECT cnpj_basico FROM ig_map)
  AND ld.cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.resto_referencia)  -- não re-harvestar
ON CONFLICT (cnpj_basico) DO NOTHING;

SELECT sinal, count(*) FROM prospeccao.hunter_resto_todo WHERE cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.resto_referencia) GROUP BY 1 ORDER BY min(pri);
