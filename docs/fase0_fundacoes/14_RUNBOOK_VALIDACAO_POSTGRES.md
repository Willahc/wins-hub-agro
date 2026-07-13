# Runbook — validação PostgreSQL

## Pré-requisitos

- Docker disponível;
- imagem PostgreSQL 16 já presente localmente;
- working tree revisado e backup fora do repositório;
- nenhuma variável ou rede de produção fornecida ao harness.

## Execução isolada

```bash
cd /root/wins_agro_v1
bash scripts/fase0/test_foundation_postgres.sh
```

Opcionalmente, a imagem local pode ser definida explicitamente:

```bash
FASE0_TEST_POSTGRES_IMAGE=postgres:16-alpine \
  bash scripts/fase0/test_foundation_postgres.sh
```

O harness cria nome único, `--network none`, tmpfs de 512 MB, 768 MB de memória,
uma CPU, nenhuma porta e trap de remoção. Sem variável explícita, consulta somente
o nome da imagem do container atual por metadata; não lê env, mounts ou dados.

## Ordem validada

1. `001_foundation_schema.sql` — uma única vez;
2. `002_reference_units.sql` — idempotente;
3. `020_legacy_mapping_schema.sql` — uma única vez;
4. `030_legacy_bootstrap_idempotent.sql`;
5. `040_legacy_bootstrap_rollback.sql`;
6. `090_foundation_grants.sql` com papéis explícitos;
7. `099_foundation_schema_down.sql` somente no teste de rollback.

`010_legacy_bootstrap_template.sql` está propositalmente desabilitado.

## Condições de aprovação

- termina com `FASE0B_POSTGRES_OK`;
- versão começa por 16;
- dry-run não altera contagens;
- reapply do bootstrap cria zero itens;
- conflitos abortam e não alteram papel/organização;
- ACLs de app/readonly/PUBLIC passam;
- dependência externa faz o down abortar e restaurar a transação;
- após remover a dependência, down remove apenas `foundation`;
- tabela sintética externa e `fazenda.cliente` permanecem;
- `docker inspect` do nome temporário falha ao final porque ele foi removido.

**ABORTAR:** imagem ausente/incorreta, rede/porta/mount inesperado, readiness >30 s,
qualquer assertion, container restante ou mudança no compose de produção.
