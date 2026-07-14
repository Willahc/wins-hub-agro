-- Seed script for Phase 0D Staging Environment
\set ON_ERROR_STOP on

-- Limpa tabelas da fundação para garantir idempotência completa
DELETE FROM foundation.audit_events;
DELETE FROM foundation.legacy_farm_links;
DELETE FROM foundation.farm_access;
DELETE FROM foundation.organization_memberships;
DELETE FROM foundation.operational_farms;
DELETE FROM foundation.organizations;
DELETE FROM foundation.app_users;

-- 1. Criação de Usuários Sintéticos
-- User Owner Alfa
INSERT INTO foundation.app_users (id, public_id, auth_subject, status)
OVERRIDING SYSTEM VALUE
VALUES (1, '10000000-0000-4000-8000-000000000001', 'usr_owner_alfa', 'active');

-- User Admin Alfa
INSERT INTO foundation.app_users (id, public_id, auth_subject, status)
OVERRIDING SYSTEM VALUE
VALUES (2, '10000000-0000-4000-8000-000000000002', 'usr_admin_alfa', 'active');

-- User Technician Alfa
INSERT INTO foundation.app_users (id, public_id, auth_subject, status)
OVERRIDING SYSTEM VALUE
VALUES (3, '10000000-0000-4000-8000-000000000003', 'usr_tech_alfa', 'active');

-- User Viewer Alfa
INSERT INTO foundation.app_users (id, public_id, auth_subject, status)
OVERRIDING SYSTEM VALUE
VALUES (4, '10000000-0000-4000-8000-000000000004', 'usr_viewer_alfa', 'active');

-- User Owner Beta
INSERT INTO foundation.app_users (id, public_id, auth_subject, status)
OVERRIDING SYSTEM VALUE
VALUES (5, '20000000-0000-4000-8000-000000000001', 'usr_owner_beta', 'active');

-- User Operator Beta
INSERT INTO foundation.app_users (id, public_id, auth_subject, status)
OVERRIDING SYSTEM VALUE
VALUES (6, '20000000-0000-4000-8000-000000000002', 'usr_oper_beta', 'active');

-- User Multi Org
INSERT INTO foundation.app_users (id, public_id, auth_subject, status)
OVERRIDING SYSTEM VALUE
VALUES (7, '30000000-0000-4000-8000-000000000001', 'usr_multi_org', 'active');

-- User Sem Membership
INSERT INTO foundation.app_users (id, public_id, auth_subject, status)
OVERRIDING SYSTEM VALUE
VALUES (8, '40000000-0000-4000-8000-000000000001', 'usr_no_mem', 'active');

-- User Mem Revoked
INSERT INTO foundation.app_users (id, public_id, auth_subject, status)
OVERRIDING SYSTEM VALUE
VALUES (9, '50000000-0000-4000-8000-000000000001', 'usr_revoked', 'active');

-- User Mem Inactive
INSERT INTO foundation.app_users (id, public_id, auth_subject, status)
OVERRIDING SYSTEM VALUE
VALUES (10, '60000000-0000-4000-8000-000000000001', 'usr_inactive', 'active');

-- User Mari (System Owner)
INSERT INTO foundation.app_users (id, public_id, auth_subject, status)
OVERRIDING SYSTEM VALUE
VALUES (11, '70000000-0000-4000-8000-000000000001', 'mari@winshubagro.cloud', 'active');


-- 2. Criação de Organizações Sintéticas
-- Org Alfa
INSERT INTO foundation.organizations (id, public_id, name, slug, status)
OVERRIDING SYSTEM VALUE
VALUES (1, 'a0000000-0000-4000-8000-00000000000a', 'Organização Sintética Alfa', 'alfa', 'active');

-- Org Beta
INSERT INTO foundation.organizations (id, public_id, name, slug, status)
OVERRIDING SYSTEM VALUE
VALUES (2, 'b0000000-0000-4000-8000-00000000000b', 'Organização Sintética Beta', 'beta', 'active');

-- Org Gama (Inactive)
INSERT INTO foundation.organizations (id, public_id, name, slug, status)
OVERRIDING SYSTEM VALUE
VALUES (3, 'c0000000-0000-4000-8000-00000000000c', 'Organização Sintética Gama', 'gama', 'inactive');


-- 3. Criação de Fazendas Operacionais Privadas
-- Fazendas Alfa
INSERT INTO foundation.operational_farms (id, public_id, organization_id, name, state, municipality_code, area_ha, status)
OVERRIDING SYSTEM VALUE
VALUES (1, 'f0000000-0000-4000-8000-000000000001', 1, 'Fazenda Sintética Norte', 'SP', '3550308', 150.50, 'active');

INSERT INTO foundation.operational_farms (id, public_id, organization_id, name, state, municipality_code, area_ha, status)
OVERRIDING SYSTEM VALUE
VALUES (2, 'f0000000-0000-4000-8000-000000000002', 1, 'Fazenda Sintética Sul', 'MG', '3106200', 250.75, 'active');

INSERT INTO foundation.operational_farms (id, public_id, organization_id, name, state, municipality_code, area_ha, status)
OVERRIDING SYSTEM VALUE
VALUES (3, 'f0000000-0000-4000-8000-000000000003', 1, 'Fazenda Sintética Leste', 'PR', '4106902', 80.00, 'active');

-- Fazendas Beta
INSERT INTO foundation.operational_farms (id, public_id, organization_id, name, state, municipality_code, area_ha, status)
OVERRIDING SYSTEM VALUE
VALUES (4, 'f0000000-0000-4000-8000-000000000004', 2, 'Fazenda Sintética Oeste', 'GO', '5208707', 500.00, 'active');

INSERT INTO foundation.operational_farms (id, public_id, organization_id, name, state, municipality_code, area_ha, status)
OVERRIDING SYSTEM VALUE
VALUES (5, 'f0000000-0000-4000-8000-000000000005', 2, 'Fazenda Sintética Restrita', 'MT', '5103403', 1200.00, 'active');

-- Fazenda Inactive
INSERT INTO foundation.operational_farms (id, public_id, organization_id, name, state, municipality_code, area_ha, status)
OVERRIDING SYSTEM VALUE
VALUES (6, 'f0000000-0000-4000-8000-000000000006', 2, 'Fazenda Inactive', 'MS', '5002704', 50.00, 'inactive');


-- 4. Criação de Memberships
-- Memberships Alfa
INSERT INTO foundation.organization_memberships (id, public_id, organization_id, user_id, role, status)
OVERRIDING SYSTEM VALUE
VALUES (1, '90000000-0000-4000-8000-000000000001', 1, 1, 'owner', 'active');

INSERT INTO foundation.organization_memberships (id, public_id, organization_id, user_id, role, status)
OVERRIDING SYSTEM VALUE
VALUES (2, '90000000-0000-4000-8000-000000000002', 1, 2, 'admin', 'active');

INSERT INTO foundation.organization_memberships (id, public_id, organization_id, user_id, role, status)
OVERRIDING SYSTEM VALUE
VALUES (3, '90000000-0000-4000-8000-000000000003', 1, 3, 'technician', 'active');

INSERT INTO foundation.organization_memberships (id, public_id, organization_id, user_id, role, status)
OVERRIDING SYSTEM VALUE
VALUES (4, '90000000-0000-4000-8000-000000000004', 1, 4, 'viewer', 'active');

-- Membership Mari
INSERT INTO foundation.organization_memberships (id, public_id, organization_id, user_id, role, status)
OVERRIDING SYSTEM VALUE
SELECT 11, '90000000-0000-4000-8000-000000000011', o.id, u.id, 'owner', 'active'
  FROM foundation.organizations o, foundation.app_users u
 WHERE o.public_id = 'a0000000-0000-4000-8000-00000000000a'
   AND u.auth_subject = 'mari@winshubagro.cloud';

-- Memberships Beta
INSERT INTO foundation.organization_memberships (id, public_id, organization_id, user_id, role, status)
OVERRIDING SYSTEM VALUE
VALUES (5, '90000000-0000-4000-8000-000000000005', 2, 5, 'owner', 'active');

INSERT INTO foundation.organization_memberships (id, public_id, organization_id, user_id, role, status)
OVERRIDING SYSTEM VALUE
VALUES (6, '90000000-0000-4000-8000-000000000006', 2, 6, 'operator', 'active');

-- Multi Org (Ativa em Alfa e Beta)
INSERT INTO foundation.organization_memberships (id, public_id, organization_id, user_id, role, status)
OVERRIDING SYSTEM VALUE
VALUES (7, '90000000-0000-4000-8000-000000000007', 1, 7, 'manager', 'active');

INSERT INTO foundation.organization_memberships (id, public_id, organization_id, user_id, role, status)
OVERRIDING SYSTEM VALUE
VALUES (8, '90000000-0000-4000-8000-000000000008', 2, 7, 'operator', 'active');

-- Revoked Membership in Alfa
INSERT INTO foundation.organization_memberships (id, public_id, organization_id, user_id, role, status, revoked_at)
OVERRIDING SYSTEM VALUE
VALUES (9, '90000000-0000-4000-8000-000000000009', 1, 9, 'technician', 'revoked', now());

-- Inactive Membership in Alfa
INSERT INTO foundation.organization_memberships (id, public_id, organization_id, user_id, role, status)
OVERRIDING SYSTEM VALUE
VALUES (10, '90000000-0000-4000-8000-000000000010', 1, 10, 'technician', 'inactive');


-- 5. Atribuição de Acesso às Fazendas (Farm Access)
-- Technician Alfa -> Fazenda Sintética Norte (Active)
INSERT INTO foundation.farm_access (id, public_id, organization_id, farm_id, membership_id, access_level, status)
OVERRIDING SYSTEM VALUE
VALUES (1, '80000000-0000-4000-8000-000000000001', 1, 1, 3, 'operate', 'active');

-- Viewer Alfa -> Fazenda Sintética Sul (Active)
INSERT INTO foundation.farm_access (id, public_id, organization_id, farm_id, membership_id, access_level, status)
OVERRIDING SYSTEM VALUE
VALUES (2, '80000000-0000-4000-8000-000000000002', 1, 2, 4, 'read', 'active');

-- Operator Beta -> Fazenda Sintética Oeste (Active)
INSERT INTO foundation.farm_access (id, public_id, organization_id, farm_id, membership_id, access_level, status)
OVERRIDING SYSTEM VALUE
VALUES (3, '80000000-0000-4000-8000-000000000003', 2, 4, 6, 'operate', 'active');

-- Revoked Farm Access: Tech Alfa -> Fazenda Leste
INSERT INTO foundation.farm_access (id, public_id, organization_id, farm_id, membership_id, access_level, status, revoked_at)
OVERRIDING SYSTEM VALUE
VALUES (4, '80000000-0000-4000-8000-000000000004', 1, 3, 3, 'operate', 'revoked', now());

-- Ajusta os contadores de sequência globais
SELECT setval(pg_get_serial_sequence('foundation.app_users', 'id'), 12);
SELECT setval(pg_get_serial_sequence('foundation.organizations', 'id'), 4);
SELECT setval(pg_get_serial_sequence('foundation.operational_farms', 'id'), 7);
SELECT setval(pg_get_serial_sequence('foundation.organization_memberships', 'id'), 12);
SELECT setval(pg_get_serial_sequence('foundation.farm_access', 'id'), 5);

-- Semeando tabelas legadas para o inventário
DELETE FROM fazenda.cliente CASCADE;
INSERT INTO fazenda.cliente (id, razao_social, uf, municipio, plano_contratado) VALUES
(17, 'Fazenda Demonstração Staging', 'TO', 'Porto Nacional', 'premium');

-- Mock audit log and webauthn credentials for staging rehearsal
DELETE FROM prospeccao.audit_log;
DELETE FROM prospeccao.webauthn_credential;

INSERT INTO prospeccao.audit_log (usuario, acao, detalhe) VALUES
('mari@winshubagro.cloud', 'login_ok', 'via=passkey'),
('williamvnvn@gmail.com', 'login_ok', 'via=passkey'),
('sre@wins', 'login_ok', 'via=passkey');

INSERT INTO prospeccao.webauthn_credential (cred_id, user_email, public_key) VALUES
('cred_1', 'mari@winshubagro.cloud', 'pubkey_1'),
('cred_2', 'williamvnvn@gmail.com', 'pubkey_2');
