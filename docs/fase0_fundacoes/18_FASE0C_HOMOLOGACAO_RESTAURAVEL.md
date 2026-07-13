# Fase 0C — Homologação Restaurável

Este documento descreve a arquitetura, o isolamento e a execução do harness de homologação restaurável desenvolvido na Fase 0C.

---

## 1. Arquitetura do Ambiente Isolado

* **IMPLEMENTADO NA FASE 0C** — Rede Docker exclusiva `wins_agro_fase0c_net_<timestamp>` sem qualquer conexão com a rede de produção (`bridge` isolada de outros containers e externa).
* **IMPLEMENTADO NA FASE 0C** — Instâncias de banco de dados temporárias baseadas na imagem local `postgres:16-alpine`.
* **IMPLEMENTADO NA FASE 0C** — Volumes de dados Docker dedicados e exclusivos `wins_agro_fase0c_source_data_<timestamp>` e `wins_agro_fase0c_restore_data_<timestamp>`.
* **IMPLEMENTADO NA FASE 0C** — Nenhuma porta foi publicada no host (`-p` / `--publish` omitidos). A comunicação ocorreu exclusivamente através do roteamento da rede bridge interna.
* **IMPLEMENTADO NA FASE 0C** — Limitação de recursos aplicada aos containers (Memory: 768 MB, CPU: 1).
* **DECISÃO** — Limpeza imediata de resíduos por meio de blocos `trap` capturando `EXIT`, `INT` e `TERM` executando o script `cleanup_homologation.sh` de escopo restrito.

---

## 2. Roteiro de Execução

1. **Provisionamento do Banco de Origem (Source)**:
   - Inicializa container de origem anexado à rede e ao volume exclusivo.
   - Aplica `seed_synthetic_legacy.sql` para criar as roles, schema `fazenda` e a tabela `fazenda.cliente` com dados fictícios.
2. **Migração e Grants**:
   - Executa sequencialmente `001_foundation_schema.sql`, `002_reference_units.sql`, `020_legacy_mapping_schema.sql`, `030_legacy_bootstrap_idempotent.sql`, `040_legacy_bootstrap_rollback.sql` e `090_foundation_grants.sql`.
   - Concede privilégios explícitos ao migrador.
3. **Validação do CLI Ponta a Ponta**:
   - Testa o CLI real `bootstrap_legacy.py` via virtualenv do Python 3.12.
   - Executa dry-run, rejeição de apply sem confirmação, apply de mappings válidos, idempotência e conflitos (com rollback automático).
4. **Validação do Banco e Backup**:
   - Executa `validate_roles.sql` e `validate_foundation.sql`.
   - Gera o backup lógico `wins_agro_fase0c_backup.dump` com `pg_dump --format=custom --no-owner --no-acl`.
5. **Destruição da Origem**:
   - Encerra o container de origem e apaga seu volume de dados.
6. **Restauração em Nova Instância (Restore)**:
   - Inicializa container de restauração com rede/volume novos.
   - Pre-cria as roles globais aprovadas.
   - Executa `pg_restore --exit-on-error`.
   - Re-aplica os grants de segurança.
7. **Comparação e Gates**:
   - Executa `compare_databases.sh` que sanitiza assinaturas dinâmicas e valida igualdade de DDL/grants.
   - Valida contagens lógicas de registros e integridade das constraints na restauração.
   - Teardown completo dos recursos criados.

---

## 3. Estado de Produção e Rollout

* **NÃO TESTADO EM PRODUÇÃO** — Nenhuma migration, roles ou dados foram aplicados no banco de produção.
* **CONFIRMADO NO CÓDIGO** — A feature flag de multi-tenant `ENABLE_MULTI_TENANCY_FOUNDATION` permanece desligada por padrão no monólito.
* **VALIDAÇÃO PENDENTE** — Homologação persistente e migração de uma operação real no banco de staging.
