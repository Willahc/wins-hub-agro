-- ITEM B (jun/14): limpa matches FALSOS da genética (prospect_genetica casa por NOME).
-- Falso = match_fazenda sem relação trigram com nome fantasia NEM razão social (sim<0.10).
-- NÃO toca em razão×fantasia legítimo (Santa Dulce=São José da Barra) nem em matches que a
-- detecção antiga errou por hífen/ponto/token curto (Ipê-Branco, Boa Luz, Rio Pec, Estância JM).
-- REVERSÍVEL: não deleta — rebaixa confianca p/ 'descartar' (some do sinal) + audita o original.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS prospeccao.prospect_genetica_descartado_b (
  cnpj_basico text, match_fazenda text, nome_fazenda text, razao text,
  confianca_orig text, sim_max numeric, descartado_em timestamptz DEFAULT now());

WITH cand AS (
  SELECT g.cnpj_basico, g.match_fazenda, g.confianca AS confianca_orig,
    fn.nome_fazenda, fn.razao,
    round(greatest(similarity(upper(unaccent(g.match_fazenda)), upper(unaccent(coalesce(fn.nome_fazenda,'')))),
                   similarity(upper(unaccent(g.match_fazenda)), upper(unaccent(coalesce(fn.razao,'')))))::numeric,3) AS sim_max
  FROM prospeccao.prospect_genetica g JOIN prospeccao.fazenda_nacional fn USING(cnpj_basico)
  WHERE g.confianca <> 'descartar'
)
INSERT INTO prospeccao.prospect_genetica_descartado_b (cnpj_basico,match_fazenda,nome_fazenda,razao,confianca_orig,sim_max)
SELECT cnpj_basico, match_fazenda, nome_fazenda, razao, confianca_orig, sim_max
FROM cand WHERE sim_max < 0.10;

UPDATE prospeccao.prospect_genetica g SET confianca='descartar'
FROM prospeccao.prospect_genetica_descartado_b d
WHERE g.cnpj_basico=d.cnpj_basico AND g.match_fazenda=d.match_fazenda AND g.confianca<>'descartar';

REFRESH MATERIALIZED VIEW prospeccao.fazenda_nacional;
