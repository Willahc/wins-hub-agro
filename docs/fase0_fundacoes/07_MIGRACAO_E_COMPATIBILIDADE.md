# Migração e compatibilidade

Ordem proposta, nunca automática:

1. backup e revisão DBA;
2. aplicar `001_foundation_schema.sql` em homologação vazia;
3. validar constraints, índices, grants e rollback;
4. aplicar `002_reference_units.sql`;
5. criar organização e membership legadas com parâmetros explícitos do template
   `010_legacy_bootstrap_template.sql`;
6. mapear usuários e dados privados entidade por entidade;
7. executar backfill idempotente separado, com relatório de órfãos;
8. ativar vertical slice em homologação;
9. endurecer nullable/constraints somente após reconciliação.

**IMPLEMENTADO NESTA ETAPA:** SQL estrutural sem dados reais e rollback
`099_foundation_schema_down.sql`, utilizável apenas antes da adoção. Nenhum script
foi executado.

**DECISÃO:** não há organização default embutida. A compatibilidade Python fica
desativada e exige UUID configurado; ainda assim, membership permanece obrigatória.

**RISCO:** o rollback apaga o schema e só é aceitável em ambiente descartável ou
pré-adoção. Em produção com dados, rollback deve ser aditivo e específico.
