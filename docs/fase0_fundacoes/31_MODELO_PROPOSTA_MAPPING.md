# Modelo de Proposta de Mapping — Fase 0E1

Este documento descreve a estrutura dos objetos e arquivos de propostas gerados pela Fase 0E1.

## 1. Estrutura do Objeto de Proposta
Cada proposta de mapeamento (mapping proposal) segue o seguinte schema estrutural:

```json
{
  "proposal_id": "string (HMAC do link legado)",
  "legacy_source": "string (ex: fazenda.cliente)",
  "legacy_user_id": null,
  "legacy_client_id": "integer (ID original)",
  "proposed_organization_uuid": "string (UUID)",
  "proposed_organization_name": "string",
  "proposed_farm_uuid": "string (UUID)",
  "proposed_farm_name": "string",
  "proposed_role": "string (ex: pending_review)",
  "proposed_access_level": "string (ex: read)",
  "confidence_class": "string (A a F)",
  "evidence_codes": ["string"],
  "conflict_codes": ["string"],
  "required_human_action": "string",
  "approved": false,
  "reviewer": null,
  "reviewed_at": null,
  "review_notes": "string",
  "mapping_version": 1,
  "idempotency_key": "string (UUID)"
}
```

## 2. Regras de Transição e Idempotência
* **approved = false**: Nenhuma proposta pode iniciar pré-aprovada. A aprovação é uma decisão humana formal realizada na Fase 0E2.
* **idempotency_key**: Chave exclusiva para prevenir duplicações ao aplicar as propostas no banco final.
* **conflict_codes**: Indica se há ambiguidades críticas no registro legado, como clientes sem associação de usuários cadastrados.
