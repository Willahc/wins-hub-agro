# Evidências de Execução da Fase 0C

Este documento reúne os registros de execução, contagens, checksums e testes coletados na homologação isolada da Fase 0C.

---

## 1. Detalhes da Imagem PostgreSQL

* **CONFIRMADO NO CÓDIGO** — Imagem utilizada no container de homologação:
  - **Nome**: `postgres:16-alpine`
  - **Digest Local**: `sha256:16bc17c64a573ef34162af9298258d1aec548232985b33ed7b1eac33ba35c229`
  - **Versão Observada**: PostgreSQL `16.14`
  - **Arquitetura**: `amd64` / `linux`

---

## 2. Resultados e Logs do Bootstrap (CLI Ponta a Ponta)

* **TESTADO EM HOMOLOGAÇÃO ISOLADA** — Saídas sanitizadas coletadas durante a execução do harness orquestrador:

### Teste 1: Dry-run de Mapping Válido (Cliente 1001)
```json
{
  "blocked_actions": [],
  "conflicts": [],
  "existing": {
    "farm_accesses": 0,
    "farms": 0,
    "legacy_links": 0,
    "memberships": 0,
    "organizations": 0,
    "users": 0
  },
  "idempotency_key": "70000000-0000-4000-8000-000000000001",
  "mode": "dry-run",
  "status": "ready",
  "would_create": {
    "farm_accesses": 1,
    "farms": 1,
    "legacy_links": 1,
    "memberships": 1,
    "organizations": 1,
    "users": 1
  }
}
```

### Teste 3: Apply com Confirmação Explícita (Cliente 1001)
```json
{
  "blocked_actions": [],
  "conflicts": [],
  "created": {
    "farm_accesses": 1,
    "farms": 1,
    "legacy_links": 1,
    "memberships": 1,
    "organizations": 1,
    "users": 1
  },
  "existing": {
    "farm_accesses": 0,
    "farms": 0,
    "legacy_links": 0,
    "memberships": 0,
    "organizations": 0,
    "users": 0
  },
  "idempotency_key": "70000000-0000-4000-8000-000000000001",
  "mode": "apply",
  "status": "applied",
  "would_create": {
    "farm_accesses": 1,
    "farms": 1,
    "legacy_links": 1,
    "memberships": 1,
    "organizations": 1,
    "users": 1
  }
}
```

### Teste 4: Re-apply Idempotente (Cliente 1001)
```json
{
  "blocked_actions": [],
  "conflicts": [],
  "created": {
    "farm_accesses": 0,
    "farms": 0,
    "legacy_links": 0,
    "memberships": 0,
    "organizations": 0,
    "users": 0
  },
  "existing": {
    "farm_accesses": 1,
    "farms": 1,
    "legacy_links": 1,
    "memberships": 1,
    "organizations": 1,
    "users": 1
  },
  "idempotency_key": "70000000-0000-4000-8000-000000000001",
  "mode": "apply",
  "status": "applied",
  "would_create": {
    "farm_accesses": 0,
    "farms": 0,
    "legacy_links": 0,
    "memberships": 0,
    "organizations": 0,
    "users": 0
  }
}
```

---

## 3. Evidências do Backup Lógico

* **IMPLEMENTADO NA FASE 0C** — Características do arquivo de backup gerado:
  - **Versão do pg_dump**: `16.14`
  - **Local temporário**: `/tmp/wins_agro_fase0c_<TIMESTAMP>/wins_agro_fase0c_backup.dump`
  - **Tamanho aproximado**: `157.9 KB` (157,967 bytes)
  - **SHA-256**: `60167a22602092bcb67113784c503c010987f533f672c10c42d4772600a2e397` (valor obtido na última execução bem-sucedida)

---

## 4. Comparação e Validação Pós-Restauração

* **TESTADO EM HOMOLOGAÇÃO ISOLADA** — A comparação física e lógica produziu **MATCH TOTAL**:
  - DDL físico e Grants idênticos (após limpeza de tokens dinâmicos `\restrict`/`\unrestrict`).
  - Row counts das tabelas batendo perfeitamente:
    * `foundation.organizations`: 2
    * `foundation.app_users`: 2
    * `foundation.organization_memberships`: 2
    * `foundation.operational_farms`: 2
    * `foundation.farm_access`: 2
    * `foundation.legacy_farm_links`: 2
    * `foundation.audit_events`: 12
    * `foundation.units`: 23
    * `foundation.technical_parameters`: 0
    * `foundation.formula_definitions`: 0
    * `foundation.formula_versions`: 0

---

## 5. Resultados de Testes Automatizados

* **TESTADO EM HOMOLOGAÇÃO ISOLADA** — Execução do test suite completo:
  - Total de testes Python executados: **60**
  - Resultado: **OK** (Passagem limpa de todas as asserções de segurança, grants, isolamento e CLI).
