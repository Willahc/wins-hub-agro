-- prospeccao.lead_demanda : overlay de demanda municipal nos 200k leads
-- READ-ONLY sobre fazenda_nacional, rebanho_municipio, sicor_credito_municipio, mv_vet_supply_mun, referencia.municipio

DROP MATERIALIZED VIEW IF EXISTS prospeccao.lead_demanda;

CREATE MATERIALIZED VIEW prospeccao.lead_demanda AS
WITH
-- 1) Ponte (municipio_nome,uf) -> codigo_ibge. Chave natural, sem ambiguidade
--    (referencia.municipio e unico por (nome_normalizado,uf)).
bridge AS (
  SELECT
    m.nome_normalizado AS mun_norm,
    m.uf,
    m.codigo_ibge
  FROM referencia.municipio m
),
-- 2) SICOR investimento BOVINOS (prod 1300) acumulado 2021-2025 por municipio
sicor_bov AS (
  SELECT codigo_ibge, sum(vl_total_brl) AS vl_bovinos
  FROM prospeccao.sicor_credito_municipio
  WHERE cd_produto = '1300' AND ano BETWEEN 2021 AND 2025
  GROUP BY codigo_ibge
),
-- 3) SICOR matrizes/reprodutores (prod 7580) acumulado 2021-2025 por municipio
sicor_mat AS (
  SELECT codigo_ibge, sum(vl_total_brl) AS vl_matriz
  FROM prospeccao.sicor_credito_municipio
  WHERE cd_produto = '7580' AND ano BETWEEN 2021 AND 2025
  GROUP BY codigo_ibge
),
-- 4) Normalizadores globais (log1p p/ comprimir cauda longa)
norm AS (
  SELECT
    (SELECT max(ln(1 + greatest(matrizes_estim2024,0))) FROM prospeccao.rebanho_municipio) AS max_ln_matriz,
    (SELECT max(ln(1 + greatest(vl_bovinos,0)))         FROM sicor_bov)                    AS max_ln_sicor
),
base AS (
  SELECT
    fn.*,
    b.codigo_ibge,
    r.matrizes_estim2024            AS matrizes_municipio,
    r.bovinos_ppm2024               AS bovinos_municipio,
    COALESCE(sb.vl_bovinos, 0)      AS sicor_invest_bovinos_municipio,
    COALESCE(sm.vl_matriz, 0)       AS sicor_credito_matriz_municipio,
    (sm.vl_matriz IS NOT NULL AND sm.vl_matriz > 0) AS sicor_credito_matriz_flag,
    -- deserto vet: municipio sem nenhum veterinario registrado (n_vet=0).
    -- munis fora da mv_vet_supply_mun => desconhecido => FALSE (nao penaliza).
    COALESCE(v.n_vet = 0, FALSE)    AS deserto_vet,
    v.n_vet                         AS n_vet_municipio
  FROM prospeccao.fazenda_nacional fn
  LEFT JOIN bridge b
    ON b.mun_norm = upper(unaccent(fn.municipio)) AND b.uf = fn.uf
  LEFT JOIN prospeccao.rebanho_municipio   r  ON r.codigo_ibge  = b.codigo_ibge
  LEFT JOIN sicor_bov                      sb ON sb.codigo_ibge = b.codigo_ibge
  LEFT JOIN sicor_mat                      sm ON sm.codigo_ibge = b.codigo_ibge
  LEFT JOIN prospeccao.mv_vet_supply_mun   v  ON v.codigo_ibge  = b.codigo_ibge
)
SELECT
  base.*,
  -- score_demanda 0-1 : 60% massa de matrizes (log-norm) + 30% credito bovino SICOR (log-norm)
  --                     + 10% bonus se ha credito direcionado a matrizes (sinal de reposicao/genetica)
  round((
      0.60 * LEAST(1.0, COALESCE(ln(1 + GREATEST(matrizes_municipio,0)) / NULLIF(n.max_ln_matriz,0), 0))
    + 0.30 * LEAST(1.0, COALESCE(ln(1 + GREATEST(sicor_invest_bovinos_municipio,0)) / NULLIF(n.max_ln_sicor,0), 0))
    + 0.10 * (CASE WHEN sicor_credito_matriz_flag THEN 1 ELSE 0 END)
  )::numeric, 4) AS score_demanda,
  -- canal: 1 se ha caminho de contato direto (whatsapp/email), senao 0
  (CASE WHEN COALESCE(NULLIF(trim(whatsapp),''), NULLIF(trim(email),'')) IS NOT NULL THEN 1 ELSE 0 END) AS tem_canal,
  -- prioridade_final 0-1 (1=melhor) combinando:
  --   50% prioridade genetica ja existente (fazenda_nacional.prioridade, 1=melhor; invertida e normalizada)
  --   20% canal de contato (acionabilidade)
  --   30% score_demanda municipal
  round((
      0.50 * (1.0 - (LEAST(GREATEST(prioridade,1),5) - 1)/4.0)
    + 0.20 * (CASE WHEN COALESCE(NULLIF(trim(whatsapp),''), NULLIF(trim(email),'')) IS NOT NULL THEN 1 ELSE 0 END)
    + 0.30 * (
          0.60 * LEAST(1.0, COALESCE(ln(1 + GREATEST(matrizes_municipio,0)) / NULLIF(n.max_ln_matriz,0), 0))
        + 0.30 * LEAST(1.0, COALESCE(ln(1 + GREATEST(sicor_invest_bovinos_municipio,0)) / NULLIF(n.max_ln_sicor,0), 0))
        + 0.10 * (CASE WHEN sicor_credito_matriz_flag THEN 1 ELSE 0 END)
      )
  )::numeric, 4) AS prioridade_final
FROM base CROSS JOIN norm n;

-- Indices
CREATE INDEX lead_demanda_uf_idx              ON prospeccao.lead_demanda (uf);
CREATE INDEX lead_demanda_prioridade_final_idx ON prospeccao.lead_demanda (prioridade_final DESC);

GRANT SELECT ON prospeccao.lead_demanda TO wins_app;
