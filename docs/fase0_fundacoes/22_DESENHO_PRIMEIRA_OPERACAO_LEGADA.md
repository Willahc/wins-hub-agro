# Desenho da Primeira Operação Legada Candidata — Fase 0C

Este documento propõe o desenho técnico para a migração da primeira rota legada do monolito para a fundação multiusuário, priorizando baixo risco e segurança.

---

## 1. Escolha da Operação Candidata

* **DECISÃO** — A primeira rota escolhida é de **somente leitura**: **Listagem de Fazendas Permitidas**.
* **JUSTIFICATIVA** — Operação sem efeitos colaterais (sem alteração de saldo, movimentação de estoque ou dados pessoais sensíveis), minimizando riscos operacionais durante a validação da nova camada de autorização.
* **FORA DE ESCOPO** — Edição de dados, criação de lotes ou integração com prospecção/Cliente Inteligente.

---

## 2. Detalhamento Técnico da Migração

### Endpoint Atual (Legado)
- **Método**: `GET`
- **Rota**: `/api/fazendas`
- **Comportamento**: Retorna todas as fazendas da tabela legado `fazenda.cliente` onde o usuário atual tem acesso (hoje baseado em ID global do cookie ou sem partição por organização).

### Endpoint Futuro (Multiusuário)
- **Método**: `GET`
- **Rota**: `/api/v2/farms`
- **Contrato de Resposta**:
  ```json
  {
    "farms": [
      {
        "public_id": "40000000-0000-4000-8000-000000000001",
        "name": "Fazenda Sintética Norte",
        "area_ha": 150.0000,
        "access_level": "manage"
      }
    ]
  }
  ```

---

## 3. Fluxo de Autorização e Consulta

* **CONFIRMADO NO CÓDIGO** — O `ActorContext` é resolvido a partir do token JWT autenticado (extraído do cookie `session`).
* **IMPLEMENTADO NA FASE 0C** — A consulta SQL é restrita através de joins obrigatórios entre o usuário, suas memberships ativas e a tabela de `farm_access`:

```sql
SELECT f.public_id, f.name, f.area_ha, a.access_level
FROM foundation.operational_farms f
JOIN foundation.farm_access a ON a.farm_id = f.id
JOIN foundation.organization_memberships m ON m.id = a.membership_id
WHERE m.user_id = :current_user_id
  AND m.organization_id = :active_organization_id
  AND m.status = 'active'
  AND a.status = 'active'
  AND f.status = 'active';
```

---

## 4. Estratégia de Rollout e Rollback

* **DECISÃO** — A rota `/api/v2/farms` será disponibilizada sob a Feature Flag `ENABLE_MULTI_TENANCY_FOUNDATION`.
* **COMPATIBILIDADE** — Enquanto a Feature Flag estiver desligada (padrão), as chamadas do frontend continuarão utilizando `/api/fazendas` (legado).
* **ROLLBACK** — Em caso de anomalia no ambiente de homologação persistente, a flag de ambiente pode ser desligada sem necessidade de novo deploy de código.
* **RISCO** — Baixo. Caso o banco novo falhe ou a query apresente lentidão, o monólito apenas retorna erro na consulta e pode reverter instantaneamente para o legado.
* **NÃO TESTADO EM PRODUÇÃO** — Esta migração está apenas desenhada e não foi implementada ou testada nos ambientes produtivos.
