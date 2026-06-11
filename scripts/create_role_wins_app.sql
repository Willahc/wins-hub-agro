-- Grants do role least-privilege da aplicação (auditoria 2026-06-11).
-- A app só precisa de DML nos schemas de negócio; DDL/migrações continuam via postgres.
-- O CREATE/ALTER ROLE (com a senha) é feito fora deste arquivo. Idempotente.

GRANT CONNECT ON DATABASE wins_agro TO wins_app;

GRANT USAGE ON SCHEMA public, catalogo, cnpj, cobertura, fazenda, mercado, plano, prospeccao, referencia TO wins_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA
  public, catalogo, cnpj, cobertura, fazenda, mercado, plano, prospeccao, referencia TO wins_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA
  public, catalogo, cnpj, cobertura, fazenda, mercado, plano, prospeccao, referencia TO wins_app;

-- objetos criados no futuro pelo postgres (migrações) já nascem acessíveis à app
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA
  public, catalogo, cnpj, cobertura, fazenda, mercado, plano, prospeccao, referencia
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wins_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA
  public, catalogo, cnpj, cobertura, fazenda, mercado, plano, prospeccao, referencia
  GRANT USAGE, SELECT ON SEQUENCES TO wins_app;
