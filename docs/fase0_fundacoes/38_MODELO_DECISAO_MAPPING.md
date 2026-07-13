# Modelo de Decisão de Mapping — Fase 0E2

Este documento descreve a estrutura técnica e regras de validação para as decisões de mapping tomadas pelo operador humano.

## 1. Schema do Objeto de Decisão
Cada decisão resultante do processo de revisão humana deve conter exatamente as seguintes propriedades:

```json
{
  "decision_id": "string (UUID v5 determinístico)",
  "proposal_id": "string (HMAC de identificação)",
  "source_execution_id": "string (timestamp da 0E1, ex: 20260713_165551)",
  "source_proposal_checksum": "string (SHA-256 da proposta original)",
  "original_confidence_class": "F",
  "decision": "string (REJECT / PENDING / REQUEST_OPERATIONAL_EVIDENCE / MANUAL_REGISTRATION_FUTURE)",
  "reason_codes": "string (motivos permitidos separados por vírgula)",
  "required_evidence": "string",
  "reviewer": "string",
  "reviewed_at": "string (ISO-8601 timezone-aware)",
  "review_notes": "string (anotações textuais limitadas)",
  "next_action": "string",
  "approved": false,
  "eligible_for_bootstrap": false,
  "eligible_for_backfill": false,
  "eligible_for_phase_0e3": false,
  "human_confirmation": "I_REVIEWED_THIS_PROPOSAL",
  "decision_version": 1
}
```

## 2. Regras de Integridade e Restrições de Valor
* **NENHUMA APROVAÇÃO**: O campo `approved` deve permanecer obrigatoriamente `false`. Nenhuma ferramenta ou decisão pode alterar este campo nesta fase.
* **Eligibilidade**: Todos os campos `eligible_for_bootstrap`, `eligible_for_backfill` e `eligible_for_phase_0e3` são fixados em `false` ou `0`.
* **original_confidence_class**: Deve ser estritamente `F`. A Fase 0E2 não altera a classe de confiança das propostas.
* **human_confirmation**: Deve conter exatamente a frase `"I_REVIEWED_THIS_PROPOSAL"`.
