# Critérios de Go/No-Go para Futura Homologação — Fase 0C

Este documento estabelece as condições formais para a transição da fundação multiusuário da Fase 0C para a homologação persistente.

---

## 1. Matriz de Decisão Go/No-Go

* **DECISÃO** — A transição para uma homologação persistente (Fase 0D) está aprovada como **GO**, baseando-se nos seguintes critérios comprovados:

| Critério | Condição Esperada | Status | Evidência / Comentário |
|---|---|---|---|
| **Isolamento de Redes** | Zero conexões de produção ocorridas no harness | **GO** | Rede Docker bridge isolada e sem portas publicadas. |
| **Integridade de Dados** | Restauração lógica perfeita (MATCH TOTAL) | **GO** | pg_dump / pg_restore executados com sucesso e comparados. |
| **Princípio do Menor Privilégio**| Roles de homologação sem SUPERUSER/CREATEDB | **GO** | Validação automatizada em `validate_roles.sql`. |
| **Evitação de IDOR** | Bloqueio de farm access cross-organization | **GO** | Testado via constraint de FK composta na origem. |
| **CLI Ponta a Ponta** | Execução idempotente e rollback em conflito | **GO** | Mapeamento 1001 e 2001 aplicados com sucesso; conflitos bloqueados. |
| **Limpeza do Ambiente** | Remoção de containers, volumes e redes | **GO** | Script `cleanup_homologation.sh` executado via traps sem resíduos. |
| **Sucesso do Test Suite** | 100% de aprovação nos 60 testes automatizados | **GO** | Executado via `unittest` em virtualenv isolado. |
| **Dados Sintéticos** | Uso estrito de informações sintéticas fictícias | **GO** | Nenhuma informação real de banco de produção foi exposta. |

---

## 2. Condições de NO-GO (Impeditivos)

* **NO-GO** se qualquer um dos seguintes cenários for observado:
  - Divergência física ou lógica de dados/grants após o restore.
  - Concessão de privilégios de escrita para a role `wins_agro_readonly`.
  - Concessão de privilégios de DDL ou criação de roles para a role `wins_agro_app`.
  - Exposição de senhas ou conexão DSN completa em logs.
  - Vazamento de containers ou volumes temporários no host Docker.
  - Vínculos ou mappings implícitos ou automáticos sem aprovação de duas pessoas.
  - Mistura ou mapping com a base `prospeccao.fazenda_nacional`.

---

## 3. Avaliação Geral de Prontidão

* **TESTADO EM HOMOLOGAÇÃO ISOLADA** — O harness automatizado provou que o fluxo de homologação é restaurável, seguro e imune a IDOR e elevação silenciosa de papéis.
* **NÃO TESTADO EM PRODUÇÃO** — Nenhuma das fundações ou scripts foi validada nos servidores produtivos ou com dados reais dos clientes.
