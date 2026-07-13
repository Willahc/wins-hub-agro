# Fase 0C — Homologação Restaurável

Este diretório contém os scripts necessários para a homologação restaurável da Fase 0C do WiNS Hub Agro.

## Estrutura de Arquivos

- `run_homologation.sh`: Script principal que gerencia o ciclo de vida completo (criação de rede, containers de origem e restauração, aplicação de DDL, bootstrap, testes de conflito, backup, restauração, comparação e cleanup).
- `cleanup_homologation.sh`: Script de limpeza robusto para remover containers, volumes e redes associadas à homologação.
- `seed_synthetic_legacy.sql`: SQL executado na instância de origem para criar a estrutura legado sintética `fazenda.cliente` e popular com dados de teste.
- `validate_roles.sql`: SQL para validar os privilégios das roles aprovadas (verificar grants e restrições).
- `validate_foundation.sql`: SQL executado na origem para validar restrições e auditoria.
- `validate_restore.sql`: SQL executado no banco restaurado para checar as constraints e privilégios pós-restauração.
- `compare_databases.sh`: Script para extrair metadados e comparar de forma lógica os bancos de origem e restauração.

## Execução

Para executar o harness completo de homologação:

```bash
bash scripts/fase0c/run_homologation.sh
```
