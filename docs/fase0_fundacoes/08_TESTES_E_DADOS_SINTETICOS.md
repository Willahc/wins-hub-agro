# Testes e dados sintéticos

Arquivos:

- `test_fase0_authorization.py`: papéis, memberships, escopo, IDOR e exportação;
- `test_fase0_units_parameters_formulas.py`: dimensão, Decimal, precedência e versões;
- `test_fase0_audit_sql_imports.py`: sanitização, SQL, import seguro e ausência de eval;
- `test_fase0_vertical_slice.py`: 200 lógico, auditoria, 401 e 404 cross-tenant;
- `fase0_fakes.py`: repository exclusivamente em memória.

Fixtures: Organização Alfa/Beta, Fazenda Sintética A/B e subjects sintéticos.
Não existem e-mails, documentos, IDs ou registros reais.

**DECISÃO:** unittest é obrigatório e não importa `app/main.py`. O teste de SQL é
estático; nenhuma conexão é aberta e `db._POOL` permanece `None` após imports.

**VALIDAÇÃO PENDENTE:** aplicar SQL e testar transações/FKs em PostgreSQL 16
descartável e isolado antes de homologação. Isso não foi necessário nesta etapa.
