# Resultados dos testes — Fase 0B

## Ambiente

- imagem: `postgres:16-alpine`, local;
- servidor observado: `160014`;
- rede: none;
- armazenamento: tmpfs sem volume persistente;
- portas: nenhuma;
- container: removido após cada execução, inclusive falhas.

## Cobertura PostgreSQL

**TESTADO EM POSTGRESQL DESCARTÁVEL:** schema, 11 tabelas após o mapping, índices,
FKs, checks, triggers, funções, grants, PUBLIC, roles, dry-run, apply, reapply,
conflitos de papel/organização, cross-tenant, unidade incompatível, vigência,
imutabilidade de fórmula, auditoria sensível, rollback de mapping e down estrutural.

Carga final do ensaio:

- 102 organizações;
- 502 usuários;
- 1.002 memberships;
- 5.002 fazendas;
- 5.001 farm accesses;
- 5.001 links legados;
- 10.008 eventos de auditoria.

## Resultado

- unittest no Python do host: 48 testes, OK;
- unittest no virtualenv existente: 48 testes, OK;
- compileall, `git diff --check`, shell syntax e Compose config: OK;
- harness PostgreSQL final: `FASE0B_POSTGRES_OK`;
- bootstrap inicial: seis entidades e seis auditorias;
- reexecução: zero duplicatas;
- alteração de papel e organização: bloqueadas com rollback;
- rollback explícito: link e acesso revogados, duas auditorias preservadas;
- schema estrutural reaplicado: rejeitado;
- referência de unidades reaplicada: 23 unidades, sem duplicação;
- down com view externa dependente: rejeitado e totalmente revertido;
- down após retirada da view: foundation removido;
- objetos `fazenda` e `external_synthetic`: preservados.

Durante a construção, o harness detectou e permitiu corrigir: representação `{}` de
port bindings, uso de variável psql em `-c`, falta de tenant Beta na fixture e
consulta incorreta do pseudo-role PUBLIC. Todas as execuções falhas removeram o
container; o resultado final passou.

**NÃO TESTADO EM PRODUÇÃO:** migrations, mappings reais, locks/tempo com volume real,
backup/restore e nomes finais de roles.
