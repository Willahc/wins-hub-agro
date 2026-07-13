# Rollout e feature flags

`ENABLE_MULTI_TENANCY_FOUNDATION` registra somente o router privado
`/api/v1/foundation`. Default: desligado. Quando ligado, sessão, membership e
fazenda continuam obrigatórias; não existe allow-all.

`ENABLE_LEGACY_ORGANIZATION_COMPATIBILITY` também é desligado por padrão e exige
`LEGACY_ORGANIZATION_PUBLIC_ID`. Não cria entidade, não faz backfill e não dispensa
membership.

Sequência: unit tests → revisão SQL → PostgreSQL descartável → homologação → criar
tenants sintéticos → smoke/IDOR → plano de observabilidade → pequena coorte →
migração progressiva de endpoints. Reverter a flag remove apenas a rota nova; não
reverte dados.

**FORA DE ESCOPO:** editar `.env`, ativar flags, aplicar migration, rebuild,
restart ou deploy.
