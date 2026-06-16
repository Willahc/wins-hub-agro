-- ============================================================================
-- promote_from_rfb.sql
-- Promove os leads do "PONTO CEGO DAS HOLDINGS" para prospeccao.cnpj_rural +
-- prospeccao.lead_decisor DIRETO dos dumps RFB já carregados em staging.
-- SEM BrasilAPI (rate limit ~30h). Idempotente (UPSERT). Re-rodável.
--
-- FONTES:
--   cnpj.stg_estab_holding  (Estabelecimento RFB, c0..c29) — só CNAE holding
--   cnpj.stg_empresas_full  (Empresa RFB, c0..c6)          — razão/natureza/capital/porte
--   prospeccao.holding_blind_spot (Vetor A — sócio agro em comum)
--   referencia.municipio (codigo_tom = código municipal RFB → nome/uf/codigo_ibge)
--
-- DOIS CONJUNTOS:
--   1. A∩B  -> tipo='HOLDING/AB'    (blind_spot ∩ CNAE holding)
--   2. B-puro tipo-Lamão -> tipo='HOLDING/NOME'
--      (CNAE holding + nome_fantasia agro, NÃO em blind_spot)
--
-- NOTAS DE LAYOUT (verificadas no banco em 2026-06-16):
--   * c11 (CNAE) vem SEM separadores: '6810201' (não '6810-2/01').
--   * c5 (situação cadastral): 02=ATIVA 08=BAIXADA 04=INAPTA 03=SUSPENSA 01=NULA.
--   * c20 (município) = referencia.municipio.codigo_tom.
--   * stg_empresas_full pode ainda estar carregando → LEFT JOIN (não some o lead;
--     campos da empresa entram NULL e o ON CONFLICT UPDATE preenche no re-run).
--   * LIMITES varchar de cnpj_rural (TRUNCADOS p/ não estourar — bug recorrente):
--       natureza_juridica(10) cnae_principal(10) porte(10) situacao(20) uf(2)
-- ============================================================================

-- ---------------------------------------------------------------------------
-- CTE base: matrizes (c3='1') com CNAE de holding, montando o CNPJ14 e
-- normalizando os campos a partir do estabelecimento + (left join) empresa.
-- ---------------------------------------------------------------------------
WITH estab AS (
  SELECT
    e.c0                                              AS cnpj_basico,
    -- CNPJ14 = basico(8) + ordem(4) + dv(2), zero-padded
    lpad(e.c0,8,'0') || lpad(coalesce(e.c1,'0001'),4,'0') || lpad(coalesce(e.c2,'00'),2,'0') AS cnpj14,
    nullif(btrim(e.c4),'')                            AS nome_fantasia,
    e.c11                                             AS cnae_raw,
    e.c5                                              AS situacao_cod,
    e.c10                                             AS data_inicio,
    nullif(btrim(e.c14),'')                           AS logradouro,
    nullif(btrim(e.c15),'')                           AS numero,
    nullif(btrim(e.c16),'')                           AS complemento,
    nullif(btrim(e.c17),'')                           AS bairro,
    nullif(btrim(e.c18),'')                           AS cep,
    upper(left(nullif(btrim(e.c19),''),2))            AS uf,
    e.c20                                             AS mun_cod,
    -- telefone = ddd1+tel1 (cai p/ ddd2+tel2 se o primeiro estiver vazio)
    coalesce(
      nullif(btrim(coalesce(e.c21,'')) || btrim(coalesce(e.c22,'')),''),
      nullif(btrim(coalesce(e.c23,'')) || btrim(coalesce(e.c24,'')),'')
    )                                                 AS telefone,
    lower(nullif(btrim(e.c27),''))                    AS email
  FROM cnpj.stg_estab_holding e
  WHERE e.c3 = '1'                       -- só MATRIZ
    AND e.c11 ~ '^(6810|6462|6463)'      -- CNAE de holding
),
-- conjunto A∩B
ab AS (
  SELECT b.cnpj_basico, 'HOLDING/AB'::text AS tipo
  FROM prospeccao.holding_blind_spot b
  WHERE EXISTS (SELECT 1 FROM estab x WHERE x.cnpj_basico = b.cnpj_basico)
),
-- conjunto B-puro tipo-Lamão (nome agro, fora do blind_spot)
bnome AS (
  SELECT x.cnpj_basico, 'HOLDING/NOME'::text AS tipo
  FROM estab x
  WHERE x.nome_fantasia ~* 'FAZEND|AGROPEC|PECUAR|RURAL|AGRO|CABANH|HARAS|NELORE|ANGUS|\mGADO\M'
    AND NOT EXISTS (SELECT 1 FROM prospeccao.holding_blind_spot b WHERE b.cnpj_basico = x.cnpj_basico)
    AND NOT EXISTS (SELECT 1 FROM ab a WHERE a.cnpj_basico = x.cnpj_basico)
),
alvo AS (
  SELECT cnpj_basico, tipo FROM ab
  UNION ALL
  SELECT cnpj_basico, tipo FROM bnome
),
-- junta tudo: estab (sempre existe) + empresa (left) + município (left)
src AS (
  SELECT
    a.cnpj_basico,
    a.tipo,
    e.cnpj14,
    e.nome_fantasia,
    e.cnae_raw,
    e.situacao_cod,
    e.data_inicio,
    e.logradouro, e.numero, e.complemento, e.bairro, e.cep,
    e.uf,
    e.telefone, e.email,
    emp.c1                                  AS razao_social,
    left(emp.c2,10)                         AS natureza_juridica,   -- varchar(10)
    -- capital_social: troca vírgula decimal por ponto; só numérico
    CASE WHEN replace(emp.c4,',','.') ~ '^[0-9]+(\.[0-9]+)?$'
         THEN replace(emp.c4,',','.')::numeric END  AS capital_social,
    left(emp.c5,10)                         AS porte_cod,           -- varchar(10)
    m.nome                                  AS municipio_nome,
    lpad(m.codigo_ibge::text,7,'0')         AS codigo_ibge_mun
  FROM alvo a
  JOIN estab e               ON e.cnpj_basico = a.cnpj_basico
  LEFT JOIN cnpj.stg_empresas_full emp ON emp.c0 = a.cnpj_basico
  LEFT JOIN referencia.municipio m
         ON m.codigo_tom = nullif(e.mun_cod,'')::int
),
-- formata os campos derivados / traduções, respeitando limites varchar
final AS (
  SELECT
    cnpj_basico,
    cnpj14,
    razao_social,
    nome_fantasia,
    natureza_juridica,
    -- CNAE: formata 7 dígitos -> NNNN-N/NN, trunca em 10
    left(
      CASE WHEN cnae_raw ~ '^[0-9]{7}$'
           THEN substr(cnae_raw,1,4)||'-'||substr(cnae_raw,5,1)||'/'||substr(cnae_raw,6,2)
           ELSE cnae_raw END
    ,10)                                            AS cnae_principal,
    capital_social,
    -- porte código RFB -> rótulo, trunca em 10
    left(CASE porte_cod
           WHEN '01' THEN 'ME'
           WHEN '03' THEN 'EPP'
           WHEN '05' THEN 'DEMAIS'
           WHEN '00' THEN 'N/I'
           ELSE coalesce(porte_cod,'') END ,10)     AS porte,
    -- situação cadastral estab -> rótulo, trunca em 20
    left(CASE situacao_cod
           WHEN '02' THEN 'ATIVA'
           WHEN '08' THEN 'BAIXADA'
           WHEN '04' THEN 'INAPTA'
           WHEN '03' THEN 'SUSPENSA'
           WHEN '01' THEN 'NULA'
           ELSE coalesce(situacao_cod,'') END ,20)  AS situacao,
    -- data_abertura AAAAMMDD -> date (8 dígitos válidos)
    CASE WHEN data_inicio ~ '^[0-9]{8}$' AND data_inicio <> '00000000'
         THEN to_date(data_inicio,'YYYYMMDD') END   AS data_abertura,
    left(cep,10)                                     AS cep,
    left(logradouro,300)                             AS logradouro,
    left(numero,20)                                  AS numero,
    left(complemento,100)                            AS complemento,
    left(bairro,100)                                 AS bairro,
    left(municipio_nome,100)                         AS municipio,
    left(uf,2)                                       AS uf,
    codigo_ibge_mun,
    left(telefone,30)                                AS telefone,
    left(email,150)                                  AS email,
    tipo
  FROM src
)
-- ===========================================================================
-- UPSERT 1: prospeccao.cnpj_rural  (CADASTRO)
-- ===========================================================================
, ins_rural AS (
  INSERT INTO prospeccao.cnpj_rural AS t (
    cnpj, razao_social, nome_fantasia, natureza_juridica, cnae_principal,
    capital_social, porte, situacao, data_abertura,
    cep, logradouro, numero, complemento, bairro, municipio, uf, codigo_ibge_mun,
    telefone, email, coletado_em
  )
  SELECT
    cnpj14, razao_social, nome_fantasia, natureza_juridica, cnae_principal,
    capital_social, porte, situacao, data_abertura,
    cep, logradouro, numero, complemento, bairro, municipio, uf, codigo_ibge_mun,
    telefone, email, now()
  FROM final
  ON CONFLICT (cnpj) DO UPDATE SET
    -- só sobrescreve com valor não-nulo (não apaga o que já existe, ex.: dossiê Lamão)
    razao_social      = coalesce(EXCLUDED.razao_social,      t.razao_social),
    nome_fantasia     = coalesce(EXCLUDED.nome_fantasia,     t.nome_fantasia),
    natureza_juridica = coalesce(EXCLUDED.natureza_juridica, t.natureza_juridica),
    cnae_principal    = coalesce(EXCLUDED.cnae_principal,    t.cnae_principal),
    capital_social    = coalesce(EXCLUDED.capital_social,    t.capital_social),
    porte             = coalesce(EXCLUDED.porte,             t.porte),
    situacao          = coalesce(EXCLUDED.situacao,          t.situacao),
    data_abertura     = coalesce(EXCLUDED.data_abertura,     t.data_abertura),
    cep               = coalesce(EXCLUDED.cep,               t.cep),
    logradouro        = coalesce(EXCLUDED.logradouro,        t.logradouro),
    numero            = coalesce(EXCLUDED.numero,            t.numero),
    complemento       = coalesce(EXCLUDED.complemento,       t.complemento),
    bairro            = coalesce(EXCLUDED.bairro,            t.bairro),
    municipio         = coalesce(EXCLUDED.municipio,         t.municipio),
    uf                = coalesce(EXCLUDED.uf,                t.uf),
    codigo_ibge_mun   = coalesce(EXCLUDED.codigo_ibge_mun,   t.codigo_ibge_mun),
    telefone          = coalesce(EXCLUDED.telefone,          t.telefone),
    email             = coalesce(EXCLUDED.email,             t.email),
    coletado_em       = now()
  RETURNING 1
)
-- ===========================================================================
-- UPSERT 2: prospeccao.lead_decisor  (CADASTRO; QSA/decisor fica p/ depois)
-- ===========================================================================
INSERT INTO prospeccao.lead_decisor AS t (
  cnpj_basico, cnpj14, razao, uf, municipio, tipo, situacao_viva, porte, enriched_at
)
SELECT
  cnpj_basico, cnpj14, razao_social, uf, municipio, tipo, situacao, porte, now()
FROM final
ON CONFLICT (cnpj_basico) DO UPDATE SET
  cnpj14        = coalesce(EXCLUDED.cnpj14,        t.cnpj14),
  razao         = coalesce(EXCLUDED.razao,         t.razao),
  uf            = coalesce(EXCLUDED.uf,            t.uf),
  municipio     = coalesce(EXCLUDED.municipio,     t.municipio),
  -- NÃO sobrescreve um tipo "rico" (ex.: MANUAL/DOSSIE da Lamão) com HOLDING/*:
  tipo          = CASE WHEN t.tipo IN ('MANUAL/DOSSIE') THEN t.tipo ELSE EXCLUDED.tipo END,
  situacao_viva = coalesce(EXCLUDED.situacao_viva, t.situacao_viva),
  porte         = coalesce(EXCLUDED.porte,         t.porte),
  enriched_at   = now();

-- ===========================================================================
-- RELATÓRIO (não muda dados) — quantos por tipo entraram em cada tabela.
-- ===========================================================================
SELECT tipo, count(*) AS leads
FROM prospeccao.lead_decisor
WHERE tipo IN ('HOLDING/AB','HOLDING/NOME')
GROUP BY tipo ORDER BY tipo;
