# Roles e Grants Aprovados — Fase 0C

Este documento oficializa os papéis e privilégios PostgreSQL aprovados para a fundação multiusuário do WiNS Hub Agro.

---

## 1. Nomes e Atributos das Roles

* **DECISÃO** — Aprovação definitiva das seguintes roles no ambiente de homologação:

| Nome da Role | LOGIN | SUPERUSER | CREATEDB | CREATEROLE | Finalidade |
|---|---|---|---|---|---|
| `wins_agro_migrator` | Sim | Não | Não | Não | Executar migrations DDL e alterar o schema. |
| `wins_agro_app` | Sim | Não | Não | Não | Executar operações DML da aplicação em tempo de execução. |
| `wins_agro_readonly` | Sim | Não | Não | Não | Realizar consultas analíticas e relatórios (Read-Only). |

* **IMPLEMENTADO NA FASE 0C** — Todas as roles são configuradas como `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION` para garantir o princípio do menor privilégio.

---

## 2. Matriz de Privilégios (Grants)

### `wins_agro_migrator` (Dono Funcional do Schema)
* **CREATE/USAGE** no schema `foundation`.
* Acesso completo a todos os objetos do schema `foundation` (DDL).
* **USAGE** no schema legado `fazenda` e **SELECT/REFERENCES** na tabela `fazenda.cliente` para possibilitar criação e verificação de FKs de mapeamento.

### `wins_agro_app` (Usuário Operacional da API)
* **USAGE** no schema `foundation`.
* **SELECT, INSERT, UPDATE, DELETE** nas tabelas operacionais:
  - `foundation.app_users`
  - `foundation.organizations`
  - `foundation.organization_memberships`
  - `foundation.operational_farms`
  - `foundation.farm_access`
  - `foundation.technical_parameters`
  - `foundation.formula_definitions`
  - `foundation.formula_versions`
* **INSERT** apenas (sem UPDATE/DELETE) em `foundation.audit_events`.
* **USAGE, SELECT** em todas as sequences do schema `foundation`.
* Não possui permissão de DDL (CREATE, ALTER, DROP) no schema `foundation`.
* Não possui permissão de EXECUTE nas funções privilegiadas de bootstrap (`process_legacy_mapping` e `revoke_legacy_mapping`).

### `wins_agro_readonly` (Relatórios e Analítico)
* **USAGE** no schema `foundation`.
* **SELECT** apenas em todas as tabelas e sequences do schema `foundation`.
* Sem qualquer permissão de escrita (INSERT, UPDATE, DELETE).
* Sem permissão de EXECUTE em funções mutáveis do schema `foundation`.

### `PUBLIC` (Acesso Anônimo/Geral)
* **REVOKE ALL** — Removido todo e qualquer privilégio do pseudo-papel `PUBLIC` no schema `foundation` (incluindo tabelas, sequences e funções).

---

## 3. Validação e Testes de Acesso

* **TESTADO EM HOMOLOGAÇÃO ISOLADA** — Os scripts `validate_roles.sql` e `test_fase0c_homologation.py` garantem de forma automatizada que:
  - Nenhuma role consiga privilégios extras indesejados.
  - A role `readonly` falhe ao tentar escrever.
  - A role `app` falhe ao tentar alterar DDL ou rodar bootstrap.
  - O pseudo-papel `PUBLIC` não tenha acesso a nenhuma estrutura privada.
* **NÃO TESTADO EM PRODUÇÃO** — Nenhuma role foi provisionada no cluster produtivo.
