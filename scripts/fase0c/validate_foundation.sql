-- Validação pós-bootstrap da Fase 0C
\set ON_ERROR_STOP on
BEGIN;

-- 1. Valida integridade e constraints básicas
DO $$
DECLARE
  v_count integer;
BEGIN
  -- Verifica organizações
  SELECT count(*) INTO v_count FROM foundation.organizations;
  IF v_count = 0 THEN
    RAISE EXCEPTION 'ERRO: nenhuma organização criada no bootstrap';
  END IF;

  -- Verifica auditoria
  SELECT count(*) INTO v_count FROM foundation.audit_events;
  IF v_count = 0 THEN
    RAISE EXCEPTION 'ERRO: nenhum evento de auditoria registrado';
  END IF;

  -- Valida ausência de campos sensíveis no metadados de auditoria (conforme CONSTRAINT check)
  IF EXISTS (
    SELECT 1 FROM foundation.audit_events
    WHERE metadata ?| ARRAY['password','senha','token','secret','cookie','authorization','credential','full_payload']
  ) THEN
    RAISE EXCEPTION 'ERRO: Campos sensíveis ou proibidos encontrados no metadata de auditoria';
  END IF;

  -- Valida se os eventos esperados foram criados
  IF NOT EXISTS (SELECT 1 FROM foundation.audit_events WHERE action = 'organization.created') THEN
    RAISE EXCEPTION 'ERRO: auditoria de organization.created ausente';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM foundation.audit_events WHERE action = 'membership.created') THEN
    RAISE EXCEPTION 'ERRO: auditoria de membership.created ausente';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM foundation.audit_events WHERE action = 'farm.created') THEN
    RAISE EXCEPTION 'ERRO: auditoria de farm.created ausente';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM foundation.audit_events WHERE action = 'farm.access_granted') THEN
    RAISE EXCEPTION 'ERRO: auditoria de farm.access_granted ausente';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM foundation.audit_events WHERE action = 'legacy_farm_link.created') THEN
    RAISE EXCEPTION 'ERRO: auditoria de legacy_farm_link.created ausente';
  END IF;

  -- Valida que as FKs impedem cross-tenant de farm access (teste conceitual na transação)
  BEGIN
    INSERT INTO foundation.farm_access
      (public_id, organization_id, farm_id, membership_id, access_level, status)
    SELECT '99000000-0000-4000-8000-000000000099', ob.id, fa.id, ma.id, 'read', 'active'
      FROM foundation.organizations oa
      JOIN foundation.organization_memberships ma ON ma.organization_id = oa.id
      CROSS JOIN foundation.organizations ob
      JOIN foundation.operational_farms fa ON fa.organization_id = ob.id
      WHERE oa.id <> ob.id LIMIT 1;
    RAISE EXCEPTION 'ERRO: Inserção de farm access com cruzamento de organização foi aceita incorretamente';
  EXCEPTION WHEN foreign_key_violation THEN
    RAISE NOTICE 'SUCESSO: Tentativa de farm access cross-organization foi rejeitada pela FK composta';
  END;

  RAISE NOTICE 'VALIDACAO FOUNDATION OK: Integridade dos dados, constraints e auditoria validadas.';
END;
$$;

COMMIT;
