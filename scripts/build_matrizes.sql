-- build_matrizes.sql
-- Materializa as fêmeas (matrizes) que hoje só existem como texto de pedigree
-- (mae_registro/mae_nome) dentro das linhas dos touros em mercado.reprodutor.
-- Tudo reversível: fonte_programa='pedigree_dam'.
--   Reverter: DELETE FROM mercado.reprodutor WHERE fonte_programa='pedigree_dam';
--             (o mae_id dos touros volta a NULL via FK ON DELETE? não há cascade,
--              então antes do delete: UPDATE ... SET mae_id=NULL WHERE mae_id IN (...))
BEGIN;

-- 0) Colunas de localização (UF/município). Aditivas; preenchidas p/ rebanho real
--    do cliente (loader). Catálogo genético não publica UF por animal.
ALTER TABLE mercado.reprodutor ADD COLUMN IF NOT EXISTS uf char(2);
ALTER TABLE mercado.reprodutor ADD COLUMN IF NOT EXISTS municipio varchar(120);

-- 1) Inserir uma matriz por (mae_registro, raca). Nome, pai (= avô materno do
--    touro) e fazenda de origem escolhidos por moda entre os filhos.
WITH dam_src AS (
  SELECT
    r.mae_registro AS registro,
    r.raca_id,
    mode() WITHIN GROUP (ORDER BY r.mae_nome) AS nome,
    mode() WITHIN GROUP (ORDER BY r.avo_materno_registro)
      FILTER (WHERE r.avo_materno_registro IS NOT NULL AND r.avo_materno_registro <> '') AS pai_registro,
    mode() WITHIN GROUP (ORDER BY r.avo_materno_nome)
      FILTER (WHERE r.avo_materno_nome IS NOT NULL AND r.avo_materno_nome <> '') AS pai_nome,
    mode() WITHIN GROUP (ORDER BY r.fazenda_origem)
      FILTER (WHERE r.fazenda_origem IS NOT NULL AND r.fazenda_origem <> '') AS fazenda_origem
  FROM mercado.reprodutor r
  WHERE r.mae_registro IS NOT NULL AND r.mae_registro <> ''
  GROUP BY r.mae_registro, r.raca_id
)
INSERT INTO mercado.reprodutor
  (registro, nome, especie_codigo, raca_id, sexo,
   pai_registro, pai_nome, fazenda_origem, fonte_referencia, fonte_programa, coletado_em)
SELECT
  registro,
  COALESCE(NULLIF(nome, ''), 'MATRIZ ' || registro),
  'BOV', raca_id, 'F',
  pai_registro, pai_nome, fazenda_origem,
  'Pedigree Dam (derived)', 'pedigree_dam', now()
FROM dam_src
ON CONFLICT (registro, raca_id) DO NOTHING;

-- 1b) Propaga fazenda de origem às matrizes já existentes (re-runs / sem fazenda).
UPDATE mercado.reprodutor dam SET fazenda_origem = src.fazenda
FROM (
  SELECT mae_registro, raca_id,
         mode() WITHIN GROUP (ORDER BY fazenda_origem)
           FILTER (WHERE fazenda_origem IS NOT NULL AND fazenda_origem <> '') AS fazenda
  FROM mercado.reprodutor
  WHERE mae_registro IS NOT NULL AND mae_registro <> ''
  GROUP BY mae_registro, raca_id
) src
WHERE dam.fonte_programa = 'pedigree_dam'
  AND dam.registro = src.mae_registro AND dam.raca_id = src.raca_id
  AND dam.fazenda_origem IS DISTINCT FROM src.fazenda AND src.fazenda IS NOT NULL;

-- 2) Grafo mãe->filho: ligar mae_id dos touros à matriz correspondente
--    (match por registro+raca; UNIQUE garante 1 linha por chave).
UPDATE mercado.reprodutor child
SET    mae_id = dam.id
FROM   mercado.reprodutor dam
WHERE  child.mae_registro IS NOT NULL AND child.mae_registro <> ''
  AND  dam.registro = child.mae_registro
  AND  dam.raca_id  = child.raca_id
  AND  child.id <> dam.id
  AND  child.mae_id IS DISTINCT FROM dam.id;

-- 3) Pai da matriz = avô materno (touro que já está no catálogo), quando existir.
UPDATE mercado.reprodutor dam
SET    pai_id = sire.id
FROM   mercado.reprodutor sire
WHERE  dam.fonte_programa = 'pedigree_dam'
  AND  dam.pai_registro IS NOT NULL AND dam.pai_registro <> ''
  AND  sire.registro = dam.pai_registro
  AND  sire.raca_id  = dam.raca_id
  AND  sire.id <> dam.id
  AND  dam.pai_id IS DISTINCT FROM sire.id;

-- 4) View de mérito materno: cada matriz com a performance da progênie.
--    Não toca em mercado.avaliacao -> matching/arbitragem de touros intactos.
DROP VIEW IF EXISTS mercado.v_matriz;
CREATE VIEW mercado.v_matriz AS
WITH iqgg AS (
  SELECT reprodutor_id, MAX(valor) AS iqgg
  FROM   mercado.avaliacao
  WHERE  caracteristica_id = 20            -- IQGg
  GROUP  BY reprodutor_id
)
SELECT
  dam.id, dam.registro, dam.nome, dam.raca_id, ra.sigla AS raca_sigla,
  dam.pai_registro, dam.pai_nome, dam.pai_id, dam.fonte_referencia, dam.fonte_programa,
  dam.fazenda_origem, dam.uf, dam.municipio,
  COUNT(f.id)                                            AS filhos_touros,
  COUNT(f.id) FILTER (WHERE iq.iqgg IS NOT NULL)         AS filhos_avaliados,
  ROUND(AVG(iq.iqgg), 2)                                 AS iqgg_medio_filhos,
  ROUND(MAX(iq.iqgg), 2)                                 AS iqgg_melhor_filho,
  ROUND(own.iqgg, 2)                                     AS iqgg_proprio,
  -- mérito exibido: progênie quando há filhos avaliados; senão genômico próprio
  ROUND(COALESCE(AVG(iq.iqgg), own.iqgg), 2)            AS merito_iqgg,
  CASE WHEN AVG(iq.iqgg) IS NOT NULL THEN 'progenie'
       WHEN own.iqgg     IS NOT NULL THEN 'propria'
       ELSE NULL END                                    AS merito_origem,
  array_agg(f.nome ORDER BY iq.iqgg DESC NULLS LAST)
    FILTER (WHERE f.id IS NOT NULL)                      AS filhos_nomes
FROM   mercado.reprodutor dam
JOIN   catalogo.raca ra        ON ra.id = dam.raca_id
LEFT   JOIN mercado.reprodutor f ON f.mae_id = dam.id
LEFT   JOIN iqgg iq            ON iq.reprodutor_id = f.id
LEFT   JOIN iqgg own           ON own.reprodutor_id = dam.id   -- avaliação própria da vaca
WHERE  dam.sexo = 'F'
GROUP  BY dam.id, ra.sigla, own.iqgg;

COMMIT;
