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

## Fase 0C

- `18_FASE0C_HOMOLOGACAO_RESTAURAVEL.md`: arquitetura de homologação;
- `19_RUNBOOK_BACKUP_RESTORE.md`: procedimentos de backup e restore;
- `20_ROLES_E_GRANTS_APROVADOS.md`: matriz de privilégios e roles aprovadas;
- `21_EVIDENCIAS_FASE0C.md`: dumps, hashes e logs;
- `22_DESENHO_PRIMEIRA_OPERACAO_LEGADA.md`: desenho do primeiro endpoint;
- `23_CRITERIOS_GO_NO_GO_PRODUCAO.md`: matriz de decisão.

## Fase 0D

- `24_FASE0D_VERTICAL_SLICE_FARMS_V2.md`: arquitetura do endpoint farms_v2;
- `25_CONTRATO_API_FARMS_V2.md`: especificação técnica e parâmetros da rota;
- `26_RUNBOOK_STAGING_PERSISTENTE.md`: runbook de gerência de staging;
- `27_EVIDENCIAS_FASE0D.md`: latências, planos de queries e testes HTTP;
- `28_SEGURANCA_E_IDOR_FARMS_V2.md`: controles contra IDOR e vazamentos;
- `29_GO_NO_GO_FASE0D.md`: matriz de decisão de go/no-go do staging.

## Fase 0E1

- `30_FASE0E1_INVENTARIO_READONLY.md`: arquitetura de inventário somente leitura;
- `31_MODELO_PROPOSTA_MAPPING.md`: modelo e schema da proposta de mapping;
- `32_PRIVACIDADE_E_MINIMIZACAO.md`: diretrizes de privacidade e minimização;
- `33_METODOLOGIA_CLASSIFICACAO_MAPPING.md`: classes de confiança e conflito;
- `34_EVIDENCIAS_SANITIZADAS_FASE0E1.md`: relatório público de evidências sanitizadas;
- `35_RUNBOOK_INVENTARIO_READONLY.md`: manual de execução e validação da ferramenta;
- `36_GO_NO_GO_FASE0E1.md`: matriz de decisão e parecer técnico.

## Fase 0E2

- `37_FASE0E2_REVISAO_HUMANA_OFFLINE.md`: arquitetura da revisão humana offline;
- `38_MODELO_DECISAO_MAPPING.md`: modelo e schema das decisões de mapping;
- `39_RUNBOOK_REVISAO_PRIVADA.md`: manual de procedimentos da revisão privada;
- `40_SEGURANCA_REVISAO_OFFLINE.md`: diretrizes e controles de segurança cibernética;
- `41_EVIDENCIAS_SANITIZADAS_FASE0E2.md`: relatório público de evidências sanitizadas da revisão;
- `42_GO_NO_GO_FASE0E2.md`: matriz de decisão e parecer técnico da Fase 0E2;
- `43_HANDOFF_FASE0E3.md`: diretrizes de handoff para a simulação da Fase 0E3.
