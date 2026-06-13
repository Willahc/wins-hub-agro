-- Decisores por fazenda a partir de cnpj.socio_rural (jun/13): TODOS os sócios PF nomeados,
-- com cargo + faixa etária, ranqueados por mando. Dá +decisores além do decisor_top.
CREATE OR REPLACE VIEW prospeccao.decisores_fazenda AS
WITH soc AS (
  SELECT cnpj_basico, nome_socio,
    CASE qualificacao_do_socio
      WHEN '16' THEN 'Presidente' WHEN '49' THEN 'Sócio-Adm' WHEN '05' THEN 'Administrador'
      WHEN '10' THEN 'Diretor'    WHEN '59' THEN 'Produtor Rural' WHEN '65' THEN 'Titular'
      WHEN '22' THEN 'Sócio'      WHEN '08' THEN 'Conselheiro' WHEN '30' THEN 'Sócio'
      ELSE 'Sócio' END AS cargo,
    CASE faixa_etaria
      WHEN '3' THEN '21-30' WHEN '4' THEN '31-40' WHEN '5' THEN '41-50'
      WHEN '6' THEN '51-60' WHEN '7' THEN '61-70' WHEN '8' THEN '71-80' WHEN '9' THEN '80+' END AS faixa,
    CASE qualificacao_do_socio WHEN '16' THEN 1 WHEN '49' THEN 2 WHEN '05' THEN 3
      WHEN '10' THEN 4 WHEN '65' THEN 5 WHEN '59' THEN 6 WHEN '22' THEN 7 ELSE 8 END AS rk,
    -- operador jovem (31-50) tem bônus no rank de alcance
    (faixa_etaria IN ('4','5')) AS jovem
  FROM cnpj.socio_rural
  WHERE identificador_de_socio='2' AND nome_socio ~ '\S\s+\S'
), rk AS (
  SELECT *, row_number() OVER (PARTITION BY cnpj_basico ORDER BY rk, jovem DESC, nome_socio) rn,
            count(*)     OVER (PARTITION BY cnpj_basico) n
  FROM soc
)
SELECT cnpj_basico,
  max(n) AS n_decisores,
  string_agg(nome_socio || ' (' || cargo || COALESCE(', '||faixa,'') || ')', ' | ' ORDER BY rn)
    FILTER (WHERE rn<=5) AS decisores,
  -- 1º sócio jovem 31-50 (operador provável) p/ priorizar canal
  (array_agg(nome_socio || CASE WHEN faixa IS NOT NULL THEN ' ('||faixa||')' ELSE '' END
     ORDER BY (NOT jovem), rk, rn) FILTER (WHERE jovem))[1] AS socio_jovem
FROM rk GROUP BY cnpj_basico;
