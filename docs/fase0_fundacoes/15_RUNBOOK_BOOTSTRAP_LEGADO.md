# Runbook — bootstrap legado

## Princípio

Bootstrap nunca descobre proprietário por nome, documento, CNPJ, proximidade ou
prospecção. Cada vínculo de `fazenda.cliente` é aprovado explicitamente.

## Mapping obrigatório

Revisar: usuário/subject, organização UUID/nome/slug, membership UUID/papel,
fazenda UUID/nome, access UUID/nível, link UUID, idempotency key, legacy client ID,
versão, origem, justificativa, aprovador e data com timezone.

O exemplo [sintético](../../scripts/fase0/examples/legacy_mapping.synthetic.json)
não deve ser reutilizado como dado real.

## Fluxo futuro

1. obter aprovação humana registrada e mapping revisado por duas pessoas;
2. confirmar backup/restauração e hash dos scripts;
3. executar dry-run, que é o default;
4. arquivar relatório sanitizado e revisar `existing`, `would_create`, conflitos e
   ações bloqueadas;
5. somente após aprovação usar `--apply --confirm APPLY_EXPLICIT_LEGACY_MAPPING`;
6. validar contagens, auditoria, membership, farm access e link;
7. repetir dry-run e confirmar idempotência;
8. monitorar erros de autorização e interromper diante de divergência.

Formato conceitual, sem DSN real:

```bash
python3 scripts/fase0/bootstrap_legacy.py \
  --input CAMINHO_MAPPING_REVISADO.json \
  --dsn 'DSN_EXPLICITO_DE_AMBIENTE_APROVADO'
```

Apply adiciona os argumentos de confirmação. O CLI rejeita host local, `db`, nome
do container de produção e banco conhecido de produção; nunca imprime o DSN.

## Rollback de mapping

`foundation.revoke_legacy_mapping` exige link UUID, idempotency key, ator ativo,
justificativa e UUIDs de auditoria. Dry-run é default. Apply revoga apenas o link e
o acesso concedido por aquele bootstrap; preserva usuário, organização, membership,
fazenda e auditoria.

**RISCO:** não usar rollback estrutural para desfazer mappings. `099` só é aceitável
antes de adoção ou em ambiente descartável.

**ABORTAR:** conflito, mapping incompleto, origem diferente de `fazenda.cliente`,
elevação de papel, troca de tenant, auditoria ausente ou relatório com dados não
sanitizados.
