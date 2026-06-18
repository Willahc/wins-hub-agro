-- =============================================================================
-- Otimização do banco wins_agro — 2026-06-15
-- Mudanças ADITIVAS e REVERSÍVEIS. Não altera/derruba nenhuma TABELA de produção.
-- Diagnóstico que motivou cada item está no comentário.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1) HIGIENE DE ÍNDICES — remover índices órfãos (0 scans em janela longa) e
--    duplicados. Recuperam ~456 MB e aceleram cargas/UPSERTs. REVERSÍVEL: o DDL
--    de recriação está em cada linha, caso algum relatório raro precise de volta.
-- -----------------------------------------------------------------------------

-- imovel_rural (3,3 GB; estes 3 índices = ~422 MB, idx_scan=0; tabela só sofreu
-- 61 seq scans na vida → analítico nunca exercido. PK e unique-key são mantidos).
DROP INDEX IF EXISTS prospeccao.idx_imovel_score;  -- recriar: CREATE INDEX idx_imovel_score ON prospeccao.imovel_rural USING btree (score_prospect DESC NULLS LAST);
DROP INDEX IF EXISTS prospeccao.idx_imovel_area;   -- recriar: CREATE INDEX idx_imovel_area  ON prospeccao.imovel_rural USING btree (area_pasto_ha DESC NULLS LAST);
DROP INDEX IF EXISTS prospeccao.idx_imovel_mun;    -- recriar: CREATE INDEX idx_imovel_mun   ON prospeccao.imovel_rural USING btree (codigo_ibge_mun);

-- avaliacao: índice de percentil nunca usado (33 MB; consultas filtram por reprodutor_id/caracteristica).
DROP INDEX IF EXISTS mercado.idx_avaliacao_percentil;  -- recriar: CREATE INDEX idx_avaliacao_percentil ON mercado.avaliacao(percentil);

-- vet_nome: idx_vet_nome_basico é DUPLICATA exata do vet_nome_pkey (ambos btree(cnpj_basico)).
DROP INDEX IF EXISTS prospeccao.idx_vet_nome_basico;   -- recriar: CREATE INDEX idx_vet_nome_basico ON prospeccao.vet_nome(cnpj_basico);

-- -----------------------------------------------------------------------------
-- 2) ÍNDICES FALTANTES em materialized views quentes usadas como driver de join.
--    mv_tecnico_geo: 5.839 seq scans lendo 72 M tuplas (sem índice). mv_herd_mun
--    é joinada por (nome_norm, uf) em mv_herd_geo (também sem índice).
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_mv_tecnico_geo_ibge   ON prospeccao.mv_tecnico_geo (codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_mv_herd_mun_nome_uf   ON prospeccao.mv_herd_mun (nome_norm, uf);

COMMIT;
