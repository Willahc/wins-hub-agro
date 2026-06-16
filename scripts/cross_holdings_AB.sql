-- Cruzamento dos dois vetores do ponto cego das holdings.
-- Entrada: cnpj.stg_estab_holding (Vetor B: estabelecimentos c/ CNAE holding nacional)
--          prospeccao.holding_blind_spot (Vetor A: empresas c/ sócio agro em comum)
-- Layout RFB Estabelecimento: c0=cnpj_basico c4=nome_fantasia c5=situacao(02=ativa)
--   c11=cnae_principal c19=uf c20=municipio_cod. CNAE holding = 6810/6462/6463.
\pset pager off

-- só matriz/filial com CNAE PRINCIPAL de holding (grep pode ter pego 6810 em campo secundário)
CREATE TEMP VIEW vb AS
  SELECT DISTINCT c0 AS cnpj_basico, c4 AS nome_fantasia, c11 AS cnae, c19 AS uf, c5 AS situacao
  FROM cnpj.stg_estab_holding
  WHERE c11 ~ '^(6810|6462|6463)';

\echo '=== universo Vetor B: holdings/imobiliárias no BR (CNAE principal) ==='
SELECT count(*) AS estab_holding, count(DISTINCT cnpj_basico) AS empresas_holding FROM vb;

\echo '=== A∩B : sócio agro em comum  E  CNAE holding (ALTA CONFIANÇA) ==='
SELECT count(DISTINCT b.cnpj_basico) AS alta_confianca
FROM prospeccao.holding_blind_spot b JOIN vb ON vb.cnpj_basico = b.cnpj_basico;

\echo '=== B-puro tipo-Lamão: CNAE holding + nome agro, SEM sócio agro (não estava no Vetor A) ==='
SELECT count(DISTINCT vb.cnpj_basico) AS holding_pura_agro
FROM vb
WHERE vb.nome_fantasia ~* 'FAZEND|AGROPEC|PECUAR|RURAL|AGRO|CABANH|HARAS|\bGADO\b|NELORE|ANGUS'
  AND NOT EXISTS (SELECT 1 FROM prospeccao.holding_blind_spot b WHERE b.cnpj_basico = vb.cnpj_basico);

\echo '=== a LAMÃO (21098855) aparece no Vetor B? (CNAE holding capturado) ==='
SELECT c0 AS cnpj_basico, c4 AS nome_fantasia, c11 AS cnae, c19 AS uf, c20 AS municipio_cod
FROM cnpj.stg_estab_holding WHERE c0='21098855';
