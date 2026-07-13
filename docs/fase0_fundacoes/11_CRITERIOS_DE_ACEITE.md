# Critérios de aceite

- subject inexistente retorna 401; membership ausente/inativa/revogada retorna 403;
- recurso inexistente ou cross-tenant retorna 404 com o mesmo código público;
- viewer não escreve; manager não transfere ownership; technician exige atribuição;
- trocar UUID de fazenda/animal/cliente no request não altera propriedade;
- FK composta impede `farm_access` cross-organization;
- operação auditada não confirma sucesso se auditoria falhar;
- metadata de auditoria omite senha, token, cookie e payload integral;
- conversão entre dimensões diferentes lança erro;
- massa verde → MS exige teor explícito;
- valores financeiros permanecem `Decimal` nos módulos de domínio;
- parâmetro ausente continua ausente e precedência é determinística;
- fórmula publicada não é sobrescrita e registry rejeita ID desconhecido;
- novos imports não abrem pool nem importam `app/main.py`;
- SQL não altera prospecção, não contém tenant hardcoded e não faz backfill;
- unittest, compileall, `git diff --check` e Compose config passam;
- nenhuma rota legada muda quando a flag está desligada.

**VALIDAÇÃO PENDENTE:** performance e plano de execução com volume representativo
somente em ambiente isolado/homologação.
