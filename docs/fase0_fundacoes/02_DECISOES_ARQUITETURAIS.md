# Decisões arquiteturais

1. **DECISÃO:** schema `foundation`, módulos pequenos e imports sem `app/main.py`.
2. **DECISÃO:** `operational_farms` é privado e não deriva automaticamente de
   `prospeccao.fazenda_nacional` ou `fazenda.cliente`.
3. **DECISÃO:** UUID é o identificador externo; bigint permanece interno. Não há
   `organization_id = 1` nem UUID padrão embutido.
4. **DECISÃO:** roles e permissions são enums centralizados; desconhecido nega.
5. **DECISÃO:** owner/admin possuem escopo organizacional; demais papéis exigem
   atribuição de fazenda e nível compatível.
6. **DECISÃO:** recursos filhos serão resolvidos no servidor até organização e
   fazenda antes de qualquer leitura/escrita.
7. **DECISÃO:** SQL versionado segue o padrão atual; Alembic não foi introduzido.
8. **DECISÃO:** sem RLS nesta etapa. Primeiro consolidar vínculos, testes e padrão
   de transação; reavaliar RLS com custo operacional e pool.
9. **DECISÃO:** feature flag apenas registra a nova rota. Ela não enfraquece a
   autorização e fica desligada por padrão.
10. **DECISÃO:** fórmulas apontam para funções registradas; expressões arbitrárias
    e `eval` são proibidos.

**VALIDAÇÃO PENDENTE:** revisão DBA dos tipos, grants, locks e plano de rollback
antes de aplicar qualquer SQL.
