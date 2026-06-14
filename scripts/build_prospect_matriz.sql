-- Prospects de elite pela origem das MATRIZES avaliadas (Geneplus "Fêmeas do Futuro", 19.806).
-- Quem PRODUZ matriz de elite = top comprador/vendedor de genética. Espelha prospect_genetica
-- (que é de touro), mas pelo lado fêmea. Casa fazenda_origem (núcleo) com lead_decisor; sem UF
-- no dado de matriz, então confiança vem da ESPECIFICIDADE do nome (nº de fazendas que casam).
DROP TABLE IF EXISTS prospeccao.prospect_matriz;
CREATE TABLE prospeccao.prospect_matriz AS
WITH norm AS (  -- função de núcleo inline (mesma régua do match de genética)
  SELECT cnpj_basico, razao, uf, municipio,
    btrim(regexp_replace(
      regexp_replace(lower(coalesce(razao,'')), '[^a-z0-9 ]',' ','g'),
      '\m(fazenda|faz|agropecuaria|agro|pecuaria|agropastoril|agricola|cabanha|nelore|rancho|estancia|sitio|haras|grupo|empreendimentos?|participacoes|comercial|ltda|sa|eireli|me|epp|do|da|de|dos|das|e)\M',
      ' ','g')) AS nucleo
  FROM prospeccao.lead_decisor),
ld AS (SELECT cnpj_basico, razao, uf, municipio, regexp_replace(nucleo,'\s+',' ','g') AS nucleo
       FROM norm WHERE length(btrim(nucleo))>=4),
mat AS (  -- origens de matriz agregadas
  SELECT r.fazenda_origem,
    btrim(regexp_replace(
      regexp_replace(lower(r.fazenda_origem), '[^a-z0-9 ]',' ','g'),
      '\m(fazenda|faz|agropecuaria|agro|pecuaria|agropastoril|agricola|cabanha|nelore|rancho|estancia|sitio|haras|grupo|ltda|sa|eireli|me|epp|do|da|de|dos|das|e)\M',
      ' ','g')) AS nucleo,
    count(DISTINCT r.id) AS n_matrizes,
    max(a.valor) FILTER (WHERE a.caracteristica_id=20) AS melhor_iqgg
  FROM mercado.reprodutor r
  LEFT JOIN mercado.avaliacao a ON a.reprodutor_id=r.id
  WHERE r.fonte_programa='geneplus_femea' AND r.fazenda_origem IS NOT NULL
  GROUP BY r.fazenda_origem),
matn AS (SELECT *, regexp_replace(nucleo,'\s+',' ','g') AS nuc FROM mat WHERE length(btrim(nucleo))>=4),
j AS (  -- casa matriz↔fazenda por núcleo; conta quantas fazendas casam cada núcleo (especificidade)
  SELECT m.fazenda_origem, m.n_matrizes, m.melhor_iqgg, m.nuc,
    l.cnpj_basico, l.razao, l.uf, l.municipio,
    count(*) OVER (PARTITION BY m.nuc) AS n_fazendas_casadas
  FROM matn m JOIN ld l ON l.nucleo = m.nuc)
SELECT fazenda_origem, n_matrizes, round(melhor_iqgg,2) AS melhor_iqgg,
  cnpj_basico, razao, uf, municipio,
  CASE WHEN n_fazendas_casadas=1 THEN 'alta'
       WHEN n_fazendas_casadas<=3 THEN 'media'
       WHEN n_fazendas_casadas<=8 THEN 'baixa' ELSE 'descartar' END AS confianca,
  (NOT EXISTS (SELECT 1 FROM prospeccao.prospect_genetica pg WHERE pg.cnpj_basico=j.cnpj_basico)) AS novo_vs_touro
FROM j
WHERE n_fazendas_casadas<=8;   -- corta nome genérico (9+ fazendas = coincidência)
CREATE INDEX ON prospeccao.prospect_matriz (cnpj_basico);
GRANT SELECT ON prospeccao.prospect_matriz TO wins_app;
-- relatório
SELECT confianca, count(*) fazendas, count(*) FILTER (WHERE novo_vs_touro) AS novos_vs_prospect_touro,
  sum(n_matrizes) total_matrizes
FROM prospeccao.prospect_matriz GROUP BY confianca ORDER BY 1;
