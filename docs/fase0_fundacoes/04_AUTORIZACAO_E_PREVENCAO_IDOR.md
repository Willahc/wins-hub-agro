# Autorização e prevenção de IDOR

Fluxo em `app/core/authorization.py`:

1. validar sessão e resolver `sub` para usuário no servidor;
2. buscar membership ativa pela organização solicitada;
3. validar permission do papel;
4. buscar fazenda pelo UUID e conferir sua organização;
5. para papéis restritos, conferir `farm_access` ativo;
6. para filhos, resolver resource → farm → organization no repository;
7. executar e auditar na mesma fronteira transacional quando aplicável.

Política HTTP: 401 sem identidade válida; 403 para membership/papel/atribuição
negados quando isso não revela outro tenant; 404 para inexistente ou recurso de
outra organização. Códigos estáveis incluem `unauthenticated`,
`membership_missing`, `membership_inactive`, `membership_revoked`, `role_denied`,
`farm_not_assigned`, `cross_organization_access` e `resource_not_found`.

**IMPLEMENTADO NESTA ETAPA:** `AuthorizationContext`, cache por request/service,
Protocol de repository e testes de troca de `farm_id`, `cliente_id`, animal e
exportação. O JSON do navegador nunca altera a organização do contexto.

**VALIDAÇÃO PENDENTE:** cada entidade legada exige vínculo server-side antes de
ser incorporada ao resolver genérico; o repository PostgreSQL aceita apenas
`operational_farm` nesta versão, por allowlist.
