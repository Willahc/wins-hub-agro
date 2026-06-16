-- Materializa o ponto cego das holdings a partir de cnpj.stg_socios_match.
-- staging = linhas do Sócios nacional cujo CPF mascarado bate com a base agro (over-match por CPF).
-- Aqui refinamos por (CPF + nome) e mantemos só empresas que NÃO estão na base agro.
\pset pager off

TRUNCATE prospeccao.holding_blind_spot;

WITH nac AS (  -- sócios nacionais (staging), normalizado
  SELECT c0 AS cnpj_basico, c2 AS nome_socio, c3 AS cpf, c4 AS qualif, c5 AS data_entrada
  FROM cnpj.stg_socios_match
  WHERE c1='2'                       -- pessoa física
), nomes_arriscados AS (  -- guardrail P1: nomes ultra-comuns (≥3 CPFs distintos na base agro)
  SELECT upper(btrim(nome_socio)) AS nome
  FROM cnpj.socio_rural
  WHERE identificador_de_socio='2'
  GROUP BY upper(btrim(nome_socio))
  HAVING count(DISTINCT cnpj_cpf_do_socio) >= 3
), match AS (  -- join fino contra a base agro por CPF + nome (excluindo nomes arriscados)
  SELECT n.cnpj_basico, n.nome_socio, n.cpf, n.qualif, n.data_entrada,
         s.cnpj_basico AS agro_cnpj
  FROM nac n
  JOIN cnpj.socio_rural s
    ON s.cnpj_cpf_do_socio = n.cpf
   AND upper(btrim(s.nome_socio)) = upper(btrim(n.nome_socio))
   AND s.identificador_de_socio='2'
  WHERE upper(btrim(n.nome_socio)) NOT IN (SELECT nome FROM nomes_arriscados)
), blind AS (  -- mantém só empresas FORA da base agro = o ponto cego
  SELECT m.*
  FROM match m
  WHERE NOT EXISTS (SELECT 1 FROM cnpj.empresa_rural e WHERE e.cnpj_basico = m.cnpj_basico)
)
INSERT INTO prospeccao.holding_blind_spot
  (cnpj_basico, nome_socio_comum, cpf_socio_comum, qualif_socio, data_entrada,
   agro_cnpj_basico, n_socios_agro)
SELECT cnpj_basico,
       (array_agg(nome_socio ORDER BY nome_socio))[1],
       (array_agg(cpf))[1],
       (array_agg(qualif))[1],
       (array_agg(data_entrada))[1],
       (array_agg(agro_cnpj))[1],
       count(DISTINCT cpf||'|'||nome_socio)
FROM blind
GROUP BY cnpj_basico
ON CONFLICT (cnpj_basico) DO NOTHING;

\echo '=== RESULTADO: ponto cego (empresas de sócios agro, fora da base agro) ==='
SELECT count(*) AS empresas_ponto_cego,
       count(*) FILTER (WHERE n_socios_agro>1) AS com_2mais_socios_agro
FROM prospeccao.holding_blind_spot;

\echo '=== a Lamão (21098855) entrou? ==='
SELECT * FROM prospeccao.holding_blind_spot WHERE cnpj_basico='21098855';
