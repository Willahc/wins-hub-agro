-- =====================================================================
-- WiNS Hub Agro — migração de maturidade do banco (jun/25)
-- Origem: auditoria DBA (relatório de maturidade). Rodar como `postgres`.
-- TODAS as operações foram pré-validadas como seguras para o runtime do app:
--   * staging RFB: 0 dependências em view/MV/app (pg_depend + grep main.py)
--   * índices: idx_scan=0 confirmado (pg_stat_user_indexes, stats nunca resetadas)
--   * REVOKE DELETE: app só faz DELETE em mercado.avaliacao (2x); nada em prospeccao/cnpj
-- BACKUP antes do DROP: backups_db/staging_predrop_20260625_105203.dump (1,4 GB, pg_dump -Fc)
-- =====================================================================
\set ON_ERROR_STOP on
BEGIN;

-- 1) Staging RFB esquecido em produção (~7,1 GB / 33% do cluster).
--    Re-carregável de scripts/load_rfb_empresas_par.sh quando rodar nova safra RFB.
DROP TABLE IF EXISTS cnpj.stg_empresas_full;
DROP TABLE IF EXISTS cnpj.stg_socios_match;
DROP TABLE IF EXISTS cnpj.stg_estab_holding;

-- 2) Índices mortos NÃO-PK e NÃO-constraint (idx_scan=0). ~42 MB.
--    OBS: imovel_rural_codigo_sigef_key foi DELIBERADAMENTE mantido — apesar de
--    idx_scan=0, é uma constraint UNIQUE (garante unicidade de codigo_sigef na
--    ingestão). Seu valor é integridade, não busca; não vale trocar por 191 MB.
DROP INDEX IF EXISTS prospeccao.ix_sigsif_abate_ibge;               -- 40 MB
DROP INDEX IF EXISTS prospeccao.idx_cnpjrural_cnae;
DROP INDEX IF EXISTS prospeccao.idx_cnpjrural_situ;
DROP INDEX IF EXISTS prospeccao.fazenda_nacional_canal_recomendado_idx;

-- 3) Least-privilege: a app não deleta em prospeccao/cnpj. Corta o blast-radius
--    de um eventual bug/SQLi (a app continua com SELECT/INSERT/UPDATE nesses schemas).
REVOKE DELETE ON ALL TABLES IN SCHEMA prospeccao FROM wins_app;
REVOKE DELETE ON ALL TABLES IN SCHEMA cnpj       FROM wins_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA prospeccao REVOKE DELETE ON TABLES FROM wins_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA cnpj       REVOKE DELETE ON TABLES FROM wins_app;

COMMIT;

-- 4) Recupera o espaço físico das tabelas afetadas e atualiza estatísticas.
--    (fora da transação). VACUUM normal é ONLINE e seguro em produção.
VACUUM (ANALYZE) prospeccao.imovel_rural;
VACUUM (ANALYZE) prospeccao.fazenda_area;

-- NOTA: o VACUUM FULL de imovel_rural (recupera ~600 MB de bloat) pega LOCK
-- EXCLUSIVO na tabela-núcleo e deve rodar em janela de manutenção, ou via
-- pg_repack (online). NÃO incluído aqui de propósito.
