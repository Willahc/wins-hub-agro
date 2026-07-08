# Relatório — Admin Claims

**Data/Hora:** 2026-07-08 19:13 UTC

---

## Backup Criado

```
/root/wins_agro_v1/backups_admin_claims_20260708_1913/
├── app.py
├── ci.db
├── index.html
├── validar_claim_persistencia.py
├── validar_claim_seed_publico.py
├── validar_cliente_inteligente_publico.py
└── validar_contatos_top500.py
```

## Arquivos Alterados

| Arquivo | Ação |
|---------|------|
| `/root/wins_agro_v1/ci-api/app.py` | Adicionados endpoints admin + token admin + schema migrations |
| `/root/wins_agro_v1/ci/admin-claims.html` | **Criado** — página admin de claims |
| `/root/wins_agro_v1/scripts/validar_admin_claims.py` | **Criado** — validador do admin |
| `/root/wins_agro_v1/ci-data/ci.db` | Colunas adicionadas: admin_note, verified_at, rejected_at |

## Token Admin

- **Caminho:** `/root/wins_agro_v1/ci-data/admin_token.txt`
- **Mascarado:** `kyOrkD...-2U`
- **Regra:** env `CI_ADMIN_TOKEN` > arquivo `/data/admin_token.txt` > arquivo `/root/wins_agro_v1/ci-data/admin_token.txt` > gerado automaticamente

## Endpoints Criados

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/admin/claims/health` | Health check do admin |
| GET | `/api/admin/claims` | Lista claims com filtros |
| PATCH | `/api/admin/claims/{id}` | Atualiza status de um claim |

Todos exigem header `x-admin-token`.

## Página Admin

- **URL:** `https://ci.winshubagro.cloud/admin-claims.html`
- Não aparece em menus públicos
- Acesso manual pela URL

## Colunas Adicionadas (schema)

- `admin_note TEXT`
- `verified_at TEXT`
- `rejected_at TEXT`

## Validações Executadas

- ✓ `py_compile app.py`
- ✓ `py_compile validar_admin_claims.py`
- ✓ `validar_claim_persistencia.py`
- ✓ `validar_claim_seed_publico.py`
- ✓ `validar_cliente_inteligente_publico.py`
- ✓ `validar_admin_claims.py`

## Runtime — Ativação (2026-07-08 19:31 UTC)

**Método:** `docker compose build ci-api && docker compose up -d ci-api`
**Motivo do rebuild:** restart simples retornou 404 — o container não carregou a nova imagem com apenas `docker restart`.

### Container

| Container | Status |
|-----------|--------|
| `wins_agro_v1-ci-api-1` | Up (healthy) |

### Testes Realizados

#### Sem token (401 — segurança OK):
```
HTTP/1.1 401 Unauthorized
{"detail":"token admin inválido"}
```

#### Com token — health:
```json
{"ok":true,"table_exists":true,"total_claims":0,"por_status":{},"updated_at":""}
```

#### Com token — lista:
```json
{"ok":true,"total":0,"claims":[]}
```

#### Tela admin:
- HTTP 200 OK
- Conteúdo válido: campo token, botão salvar, botão carregar, chamadas `/api/admin/claims`, header `x-admin-token`

### Campos Proibidos

Nenhum campo proibido encontrado na resposta dos endpoints admin nem na página HTML.

### Teste de PATCH

✅ **Realizado em 2026-07-08 19:38 UTC**

#### Claim temporário criado:
- **id:** 2
- **conta_id:** `teste_admin_patch`
- **place_id:** `0x216b8eef6b683f47:0x50140437c6d70efd`
- **status inicial:** `claimed`

#### Status testados:

| Status | Resultado | admin_note | verified_at | rejected_at |
|--------|-----------|------------|-------------|-------------|
| `verified` | ✅ OK | Preenchido | Preenchido | — |
| `rejected` | ✅ OK | Preenchido | Mantido | Preenchido |
| `pending_verification` | ✅ OK | Preenchido | Mantido | Mantido |
| `claimed` | ✅ OK | Preenchido | Mantido | Mantido |

#### Remoção:
- Claim temporário removido com sucesso
- `total_claims` voltou para 0
- Produção limpa

#### Backup do teste:
```
/root/wins_agro_v1/backups_teste_patch_admin_claims_20260708_193820/
├── RELATORIO_ADMIN_CLAIMS.md
├── admin-claims.html
├── app.py
└── ci.db
```

### Backup Marco Criado

```
/root/wins_agro_v1/backups_marco_admin_claims_ativo_20260708_193135/
├── RELATORIO_ADMIN_CLAIMS.md
├── admin-claims.html
├── app.py
├── ci.db
├── validar_admin_claims.py
├── validar_claim_persistencia.py
├── FLUXO_DADOS_3_CAMADAS.md
├── PLANO_INTEGRACAO_CAMADAS.md
└── CHANGELOG_CLIENTE_INTELIGENTE.md
```

### Integridade

- ✅ Nginx não alterado
- ✅ Docker Compose não alterado
- ✅ One Pages não alterado
- ✅ Prospecção não alterada
- ✅ Base Mestre não alterada
- ✅ App principal não alterado (apenas ci-api com novos endpoints)

## Token Admin

- **Caminho:** `/root/wins_agro_v1/ci-data/admin_token.txt`
- **Mascarado:** `kyOr****C-2U` (43 chars)
- **Regra:** env `CI_ADMIN_TOKEN` > arquivo `/data/admin_token.txt` > arquivo `/root/wins_agro_v1/ci-data/admin_token.txt` > gerado automaticamente

## Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/admin/claims/health` | Health check do admin |
| GET | `/api/admin/claims` | Lista claims com filtros |
| PATCH | `/api/admin/claims/{id}` | Atualiza status de um claim |

## Página Admin

- **URL:** `https://ci.winshubagro.cloud/admin-claims.html`
- Não aparece em menus públicos
- Acesso manual pela URL

## Próximos Passos

1. ~~Restart do container ci-api~~ ✅
2. ~~Testar endpoints com e sem token~~ ✅
3 ~~Acessar `https://ci.winshubagro.cloud/admin-claims.html`~~ ✅
4. ~~Inserir token no campo e salvar no navegador~~ (uso manual)
5. ~~Criar claim de teste e verificar no painel~~ ✅
6. ~~Verificar que dados sensíveis (CNPJ, score, etc.) NÃO são expostos~~ ✅
7. ~~Testar PATCH com claim temporário~~ ✅
8. ~~Remover claim temporário~~ ✅
