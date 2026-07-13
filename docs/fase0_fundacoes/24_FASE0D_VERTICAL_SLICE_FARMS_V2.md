# Fase 0D — Rota GET /api/v2/farms

Este documento descreve a implementação da primeira vertical slice real da fundação multiusuário: a listagem segura de fazendas privadas autorizadas.

---

## 1. Arquitetura do Endpoint

* **IMPLEMENTADO NA FASE 0D** — O fluxo segue o padrão arquitetural modular:
  - **Router** (`app/routers/farms_v2.py`): Recebe a requisição, valida parâmetros de paginação e status, injeta o service e define headers de Cache-Control preventivos.
  - **Service** (`app/services/farms_v2.py`): Autentica o ator, resolve a organização ativa, constrói o `AuthorizationContext`, valida permissão `farm.read` e delega consulta ao repositório.
  - **Repository** (`app/repositories/farms_v2.py`): Executa consultas SQL parametrizadas, realizando paginação eficiente (limit + 1) e filtros server-side de farm access.
  - **Schemas** (`app/schemas/farms_v2.py`): Pydantic models validando entrada/saída, garantindo o retorno de dados mínimos e ocultando IDs sequenciais internos.

---

## 2. Resolução do Contexto Organizacional

* **CONFIRMADO NO CÓDIGO** — A organização ativa é determinada exclusivamente pelo servidor com base em regras estritas:
  1. **Sem Sessão**: Retorna `HTTP 401 unauthenticated`.
  2. **Com Sessão, Sem Membership**: Retorna `HTTP 403 membership_missing`.
  3. **Uma Membership Ativa**: Auto-seleciona a organização se nenhuma for enviada no parâmetro `organization_uuid`.
  4. **Múltiplas Memberships, Sem Seletor**: Retorna `HTTP 409` com código estável `organization_context_required`.
  5. **Seletor Válido Enviado**: Seleciona a organização correspondente após certificar a existência de membership ativa.
  6. **Seletor de Organização Não Autorizada**: Retorna `HTTP 404 resource_not_found`, ocultando a existência do tenant.

---

## 3. Segurança e Prevenção de IDOR

* **CONFIRMADO NO CÓDIGO** — A autorização ocorre 100% no servidor. O cliente nunca pode ditar seu ID de usuário ou lista de fazendas permitidas na requisição.
* **DECISÃO** — Para papéis organizacionais amplos (`owner` e `admin`), a query retorna todas as fazendas da organização.
* **DECISÃO** — Para papéis limitados (`technician`, `operator`, `viewer`), o JOIN com `foundation.farm_access` restringe a listagem exclusivamente às fazendas delegadas ativas.
* **FORA DE ESCOPO** — Uso de Row Level Security (RLS) nesta fase. O isolamento lógico foi garantido no nível da aplicação e nas queries parametrizadas.
* **NÃO TESTADO EM PRODUÇÃO** — Esta vertical slice foi ativada apenas sob a feature flag `ENABLE_FARMS_V2` em ambiente de staging persistente.
