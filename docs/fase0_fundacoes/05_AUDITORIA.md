# Auditoria

`foundation.audit_events` registra request, ator, membership, organização,
fazenda, ação, entidade, resultado, origem, hashes opcionais e metadata limitada.

**IMPLEMENTADO NESTA ETAPA:** `app/domain/audit.py` usa allowlist de metadata,
elimina chaves de senha/token/cookie/segredo e recebe o cursor da transação da
operação. Na vertical slice, falha no insert impede a resposta de sucesso.

Ações previstas: `organization.created`, `membership.created`,
`membership.role_changed`, `membership.revoked`, `farm.created`,
`farm.access_granted`, `farm.access_revoked`, `authorization.denied`,
`parameter.created` e `formula.version_created`.

**DECISÃO:** não persistir payload integral, credenciais, cookie, IP bruto ou PII
desnecessária. Denials são logs estruturados com códigos e IDs técnicos.

**RISCO:** a Fase 0A não substitui o audit legado. Retenção, particionamento,
consulta administrativa e hash de IP dependem de política de privacidade.
