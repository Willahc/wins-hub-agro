-- jun/14: (1) manejo (0162803 ativo) entra no canal técnico (estabelecimento_vet, mesmas colunas);
-- (2) fazenda_deserto = classificação vet do município de cada fazenda (p/ filtro/KPI na página).
INSERT INTO cnpj.estabelecimento_vet
SELECT e.* FROM cnpj.estabelecimento_rural e
WHERE left(lpad(e.cnae_fiscal_principal::text,7,'0'),7)='0162803' AND e.situacao_cadastral='02'
  AND e.cnpj_basico NOT IN (SELECT cnpj_basico FROM cnpj.estabelecimento_vet);

DROP TABLE IF EXISTS prospeccao.fazenda_deserto;
CREATE TABLE prospeccao.fazenda_deserto AS
SELECT f.cnpj_basico, w.classificacao_vet
FROM prospeccao.fazenda_nacional f
JOIN prospeccao.v_white_space_pecuaria w ON upper(unaccent(w.nome))=upper(unaccent(f.municipio)) AND w.uf=f.uf;
CREATE INDEX ON prospeccao.fazenda_deserto(cnpj_basico);
CREATE INDEX ON prospeccao.fazenda_deserto(classificacao_vet);
GRANT SELECT ON prospeccao.fazenda_deserto TO wins_app;
