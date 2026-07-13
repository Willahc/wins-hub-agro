# Fase 0B — PostgreSQL e bootstrap legado

Base: `master` / `e5b131c5360bb566939f4aa43621c05eec5a70a0`, com a Fase 0A ainda sem commit.

## Resultado

**IMPLEMENTADO:** revisão DBA, harness PostgreSQL 16 isolado, vínculo explícito
`fazenda.cliente` → `foundation.operational_farms`, bootstrap dry-run/apply,
idempotência, conflitos, rollback conservador, grants e testes adicionais.

**TESTADO EM POSTGRESQL DESCARTÁVEL:** imagem local `postgres:16-alpine`, servidor
`160014`, rede `none`, tmpfs, nenhuma porta, nenhum volume persistente. O container
foi removido ao final.

## Correções reais da 0A

- grants deixaram de depender do papel fixo `wins_app` e foram separados;
- `PUBLIC` perdeu ACLs de schema, tabelas, sequências e funções;
- memberships e acessos passaram a unicidade parcial para preservar histórico;
- auditoria e parâmetro receberam FKs compostas contra cross-tenant;
- escopos de parâmetros ficaram mutuamente coerentes;
- unidade incompatível recebeu assertion SQL explícita;
- bootstrap 0A não idempotente foi desabilitado;
- rollback estrutural não usa mais `CASCADE`;
- versões publicadas, JSONB, hashes e metadata sensível foram validados;
- schema estrutural agora falha em reaplicação, conforme política.

## Bootstrap

O arquivo JSON é validado em Python e novamente no PostgreSQL. Somente
`source_schema=fazenda` e `source_table=cliente` são aceitos. IDs, UUIDs,
organização, papel, acesso, aprovador, justificativa e idempotency key são
explícitos. O dry-run não grava; apply exige confirmação no CLI.

**DECISÃO:** conflito não é corrigido automaticamente. Troca de organização,
fazenda, papel, nível de acesso, versão ou idempotency key aborta a transação.

**NÃO TESTADO EM PRODUÇÃO:** nenhum script foi aplicado e nenhum mapping real foi lido.
