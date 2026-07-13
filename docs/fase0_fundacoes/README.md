# Fase 0A — Fundações multiusuário

Leitura recomendada: `00_RESUMO_EXECUTIVO.md`, `02_DECISOES_ARQUITETURAIS.md`,
`04_AUTORIZACAO_E_PREVENCAO_IDOR.md`, `07_MIGRACAO_E_COMPATIBILIDADE.md` e
`12_CHECKPOINT_FASE0.md`.

**IMPLEMENTADO NESTA ETAPA:** primitives isoladas de organização, membership,
fazenda operacional, autorização, auditoria, unidades, parâmetros, fórmulas,
SQL não aplicado, vertical slice privada e testes sintéticos.

**FORA DE ESCOPO:** telas administrativas, convites, módulos produtivos, backfill,
migração em massa das rotas legadas, RLS e deploy.

## Fase 0B

- `13_FASE0B_POSTGRES_E_BOOTSTRAP.md`: resultado e correções;
- `14_RUNBOOK_VALIDACAO_POSTGRES.md`: harness isolado;
- `15_RUNBOOK_BOOTSTRAP_LEGADO.md`: dry-run, apply e rollback;
- `16_REVISAO_DBA.md`: constraints, privilégios e planos;
- `17_RESULTADOS_TESTES_FASE0B.md`: evidências sintéticas.
