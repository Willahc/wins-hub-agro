-- Inicializa schemas, roles e dados sintéticos da Fase 0C
\set ON_ERROR_STOP on
BEGIN;

-- 1. Criação das Roles Aprovadas
-- wins_agro_migrator: LOGIN, para orquestrar e rodar DDL, mas sem superuser/createdb
CREATE ROLE wins_agro_migrator WITH LOGIN PASSWORD 'migrator_synthetic_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

-- wins_agro_app: LOGIN, para operações da aplicação (DML)
CREATE ROLE wins_agro_app WITH LOGIN PASSWORD 'app_synthetic_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

-- wins_agro_readonly: LOGIN, para consultas (SELECT) apenas
CREATE ROLE wins_agro_readonly WITH LOGIN PASSWORD 'readonly_synthetic_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

-- Permite que o usuário do admin (fase0_test) herde ou gerencie essas roles no ambiente de teste
GRANT wins_agro_migrator, wins_agro_app, wins_agro_readonly TO CURRENT_USER;

-- 2. Criação do Schema e Tabelas Legadas Sintéticas
CREATE SCHEMA fazenda;
CREATE TABLE fazenda.cliente (
    id integer PRIMARY KEY CHECK (id > 0),
    nome text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Permite que a role migrator acesse fazenda.cliente para fins de REFERENCES (necessário para a FK em legacy_farm_links)
GRANT USAGE ON SCHEMA fazenda TO wins_agro_migrator;
GRANT SELECT, REFERENCES ON TABLE fazenda.cliente TO wins_agro_migrator;

-- 3. Inserção de Registros Sintéticos Permitidos
INSERT INTO fazenda.cliente (id, nome) VALUES
  (1001, 'Cliente Legado Sintético 1001'),
  (2001, 'Cliente Legado Sintético 2001');

COMMIT;
