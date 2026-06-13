-- ENRIQUECER A BASE NACIONAL (jun/13, William: "enriquecer todas as fazendas do Brasil").
-- Injeta no pipeline (hunter_resto_todo) TODA fazenda de corte com CAPITAL REAL (>0, <150M conglomerado)
-- ainda não harvestada e sem IG mapeado. Exclui o tier capital=R$0 (130.933, ~SP shell fiscal: sem
-- presença pública, render ~0). operador = decisor_top. Reusa harvest/whats/hunter sem mudar script.
INSERT INTO prospeccao.hunter_resto_todo (cnpj_basico, operador, faixa, razao, company_hint, uf, municipio, sinal, capital_mi, pri)
WITH ig_map AS (
  SELECT cnpj_basico FROM prospeccao.resto_referencia WHERE instagram<>''
  UNION SELECT cnpj_basico FROM prospeccao.top500_social WHERE instagram<>''
  UNION SELECT cnpj_basico FROM prospeccao.tecnico_social WHERE instagram<>''
  UNION SELECT cnpj_basico FROM prospeccao.candidato_zap WHERE instagram<>''
  UNION SELECT cnpj_basico FROM prospeccao.maria_pilot WHERE instagram<>''
  UNION SELECT cnpj_basico FROM prospeccao.icp527_screen WHERE COALESCE(instagram,cab_instagram)<>''
  UNION SELECT cnpj_basico FROM prospeccao.icp_media_screen WHERE cab_instagram<>''
  UNION SELECT left(regexp_replace(cnpj,'[^0-9]','','g'),8) FROM prospeccao.cabanha_zap WHERE instagram<>'' AND length(regexp_replace(cnpj,'[^0-9]','','g'))>=8
  UNION SELECT left(regexp_replace(cnpj14,'[^0-9]','','g'),8) FROM prospeccao.cabanha_extra WHERE instagram<>'' AND length(regexp_replace(coalesce(cnpj14,''),'[^0-9]','','g'))=14
)
SELECT ld.cnpj_basico, ld.decisor_top, NULL::int,
       ld.razao,
       initcap(regexp_replace(ld.razao,'\s+(LTDA|S/?A|S\.?A\.?|EIRELI|ME|EPP)\.?\s*$','','i')),
       ld.uf, ld.municipio,
       COALESCE(pg.confianca,'(sem sinal)'),
       round(em.capital_social/1e6,1),
       -- prioridade: sinal genético > capital (>=1M=6, resto=7) p/ os 6 workers atacarem o melhor 1o
       CASE pg.confianca WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baixa' THEN 3 WHEN 'descartar' THEN 4
            ELSE CASE WHEN em.capital_social>=1000000 THEN 6 ELSE 7 END END
FROM prospeccao.lead_decisor ld
JOIN cnpj.empresa_rural em ON em.cnpj_basico=ld.cnpj_basico
LEFT JOIN prospeccao.prospect_genetica pg ON pg.cnpj_basico=ld.cnpj_basico
WHERE em.capital_social > 0 AND em.capital_social < 150000000
  AND ld.razao IS NOT NULL AND ld.razao<>''
  AND ld.cnpj_basico NOT IN (SELECT cnpj_basico FROM ig_map)
  AND ld.cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.resto_referencia)
ON CONFLICT (cnpj_basico) DO NOTHING;

SELECT count(*) novas_no_pipeline FROM prospeccao.hunter_resto_todo t
WHERE t.cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.resto_referencia);
