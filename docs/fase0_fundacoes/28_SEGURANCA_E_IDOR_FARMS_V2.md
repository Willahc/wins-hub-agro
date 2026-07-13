# Segurança e Prevenção de IDOR — Farms V2

Este documento detalha os mecanismos de proteção e controles de acesso empregados no endpoint `/api/v2/farms` para mitigar vulnerabilidades de IDOR e vazamento multitenant.

---

## 1. Barreiras de Defesa e Segurança

* **CONFIRMADO NO CÓDIGO** — A listagem de fazendas está blindada por 4 barreiras de defesa sequenciais aplicadas no servidor:
  1. **Autenticação Real**: Verificação da assinatura digital do JWT extraído do cookie de sessão.
  2. **Membership Ativa**: Certificação de que o usuário possui uma vinculação ativa e não revogada com a organização solicitada.
  3. **Resolução de Organização**: A organização ativa é resolvida implicitamente pelo servidor ou filtrada rigorosamente pelo UUID fornecido, validando a membership.
  4. **Filtro de Escopo de Fazenda**: A query restringe o retorno apenas a fazendas associadas à organização do contexto e (para papéis não-administrativos) atribuídas ao usuário no catálogo `farm_access`.

---

## 2. Mitigação de IDOR (Insecure Direct Object Reference)

* **CONFIRMADO NO CÓDIGO** — O cliente não pode forçar a listagem de fazendas fornecendo parâmetros como `allowed_farm_ids`, `user_id` ou `cliente_id` no payload.
* **DECISÃO** — Caso um usuário tente listar fazendas fornecendo o `organization_uuid` de outro tenant, a aplicação retorna `HTTP 404 resource_not_found` em vez de `HTTP 403 Forbidden`, impedindo a enumeração de IDs e a descoberta de dados de terceiros.
* **DECISÃO** — A tabela pública de prospecção `prospeccao.fazenda_nacional` permaneceu completamente separada, sem qualquer join ou consulta a partir do endpoint `/api/v2/farms`.
* **TESTADO VIA HTTP NO STAGING** — Os cenários de ataque cross-tenant foram simulados no staging e resultaram em bloqueio total (retorno de 404 ou 403 correspondentes).
* **NÃO TESTADO EM PRODUÇÃO** — As regras de prevenção de IDOR foram validadas exclusivamente nas suítes de testes do ambiente de staging.
