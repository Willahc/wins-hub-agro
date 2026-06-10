-- resolve_vet_nome.sql (2026-06-11)
-- Nome do profissional (PF) por trás de cada CNPJ de vet, usando empresa_vet + socio_vet
-- (carregados por load_rfb_vet_emp_soc.sh). Espelha a lógica do decisor nacional:
--   - Empresário Individual (2135) / Produtor Rural PF (4120): razão social JÁ É o nome da pessoa.
--   - Demais (LTDA etc.): melhor SÓCIO pessoa física, ranqueado por cargo de mando.
--   - Fallback: razão social.

DROP TABLE IF EXISTS prospeccao.vet_nome;
CREATE TABLE prospeccao.vet_nome AS
WITH socio_rank AS (  -- melhor sócio PF por CNPJ (cargo de mando primeiro)
  SELECT DISTINCT ON (cnpj_basico)
         cnpj_basico, nome_socio, qualificacao_do_socio
  FROM cnpj.socio_vet
  WHERE identificador_de_socio = '2'           -- 2 = pessoa física
    AND nome_socio IS NOT NULL AND nome_socio <> ''
  ORDER BY cnpj_basico,
    CASE qualificacao_do_socio
      WHEN '49' THEN 1  -- Sócio-Administrador
      WHEN '05' THEN 2  -- Administrador
      WHEN '16' THEN 3  -- Presidente
      WHEN '10' THEN 4  -- Diretor
      WHEN '65' THEN 5  -- Titular
      WHEN '59' THEN 6  -- Produtor Rural
      WHEN '22' THEN 7  -- Sócio
      ELSE 9 END,
    nome_socio
)
SELECT e.cnpj_basico,
       e.razao_social,
       e.natureza_juridica,
       CASE
         WHEN e.natureza_juridica IN ('2135','4120') THEN e.razao_social   -- EI / Produtor PF
         WHEN s.nome_socio IS NOT NULL                THEN s.nome_socio     -- melhor sócio
         ELSE e.razao_social                                               -- fallback
       END AS nome_pf,
       CASE
         WHEN e.natureza_juridica IN ('2135','4120') THEN 'razao_EI'
         WHEN s.nome_socio IS NOT NULL                THEN 'socio'
         ELSE 'razao_fallback'
       END AS fonte_nome,
       s.qualificacao_do_socio AS socio_qualif
FROM cnpj.empresa_vet e
LEFT JOIN socio_rank s ON s.cnpj_basico = e.cnpj_basico;

ALTER TABLE prospeccao.vet_nome ADD PRIMARY KEY (cnpj_basico);
CREATE INDEX idx_vet_nome_basico ON prospeccao.vet_nome(cnpj_basico);

\echo '=== cobertura por fonte do nome ==='
SELECT fonte_nome, count(*) FROM prospeccao.vet_nome GROUP BY 1 ORDER BY 2 DESC;
\echo '=== quantos estab. de vet ATIVOS ganham nome de pessoa? ==='
SELECT count(*) estab_ativos,
  count(vn.nome_pf) com_nome,
  count(*) FILTER (WHERE vn.fonte_nome IN ('razao_EI','socio')) nome_pf_forte
FROM cnpj.estabelecimento_vet e
LEFT JOIN prospeccao.vet_nome vn ON vn.cnpj_basico=e.cnpj_basico
WHERE e.situacao_cadastral='02';
