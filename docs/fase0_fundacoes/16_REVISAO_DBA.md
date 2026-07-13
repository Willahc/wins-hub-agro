# Revisão DBA PostgreSQL 16

## DDL e concorrência

- `ON_ERROR_STOP`, transação, `lock_timeout=5s` e `statement_timeout=60s` no schema;
- schema tem owner do papel de migration e não concede `CREATE` à aplicação;
- UUIDs são fornecidos de forma controlada; nenhuma extensão foi exigida;
- `timestamptz` em eventos/vigências;
- FKs usam `NO ACTION/RESTRICT` por padrão; nada usa cascade destrutivo;
- advisory transaction lock serializa a mesma idempotency key;
- corrida entre validação e insert ainda é protegida pelas UNIQUE/FKs e aborta tudo.

## Integridade

- FK composta de farm access, parâmetros, auditoria e legacy link;
- membership/acesso têm um registro ativo por escopo e preservam históricos revogados;
- legacy source é exclusivamente `fazenda.cliente`, com FK ao ID legado;
- um cliente tem um link e uma fazenda recebe um cliente por padrão;
- published parameter/formula não pode sofrer update/delete;
- metadata de auditoria é objeto e rejeita chaves sensíveis no topo;
- hashes/checksum são hexadecimais de 64 caracteres;
- massa verde e MS têm dimensões diferentes.

## Privilégios

- `phase0_owner`: migration role sem superuser/CREATEDB/CREATEROLE;
- app: USAGE, SELECT, sequences, DML operacional selecionado e INSERT-only em audit;
- readonly: USAGE + SELECT;
- app não executa funções de bootstrap/rollback;
- PUBLIC não possui ACL no schema, objetos ou funções;
- nenhuma role recebe CREATE no schema foundation.

**VALIDAÇÃO PENDENTE:** mapear os nomes finais das roles e garantir `REFERENCES` do
papel de migration em `fazenda.cliente` antes da janela produtiva.

## Planos

- membership: unique partial index;
- farm access pontual: unique partial index;
- lista de acessos: bitmap no índice membership/status e hash join amplo;
- legacy link: unique source index;
- auditoria: bitmap no índice organização/data;
- parâmetro: índice de resolução, com sort pequeno por vigência;
- fórmula: unique formula/version em backward scan.

O scan sequencial de `operational_farms` ocorreu apenas na listagem ampla de muitas
fazendas e não justificou novo índice. Nenhum índice adicional foi criado após os
EXPLAIN.
