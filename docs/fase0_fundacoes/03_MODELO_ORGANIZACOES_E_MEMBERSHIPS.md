# Organizações, memberships e fazendas

## Estruturas

- `app_users`: liga o `sub` autenticado a uma identidade interna.
- `organizations`: tenant, UUID público, slug, status e autoria.
- `organization_memberships`: usuário, papel, estado, validade e revogação.
- `operational_farms`: propriedade privada pertencente a uma organização.
- `farm_access`: membership e fazenda na mesma organização, nível e validade.

**IMPLEMENTADO NESTA ETAPA:** dataclasses imutáveis em
`app/domain/foundation.py`; constraints e índices em
`scripts/fase0/001_foundation_schema.sql`.

Papéis: owner, admin, manager, technician, operator e viewer. Owner mantém ação
exclusiva de transferência; admin tem administração ampla; manager não gerencia
membership nem herda poder de owner; technician registra conteúdo técnico somente
nas fazendas atribuídas; operator opera; viewer lê.

**DECISÃO:** membership inativa, expirada ou revogada nega. A FK composta de
`farm_access` impede membership e fazenda de organizações diferentes.

**RISCO:** documento da fazenda é opcional e sensível. Criptografia, mascaramento,
retenção e necessidade real devem ser aprovadas antes de uso.
