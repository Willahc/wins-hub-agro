-- Rollback conservador: revoga mapping e acesso exato; preserva entidades/auditoria.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE FUNCTION foundation.revoke_legacy_mapping(
    p_link_public_id uuid,
    p_idempotency_key uuid,
    p_actor_user_public_id uuid,
    p_justification text,
    p_link_audit_public_id uuid,
    p_access_audit_public_id uuid,
    p_apply boolean DEFAULT false
)
RETURNS jsonb
LANGUAGE plpgsql
VOLATILE
SECURITY INVOKER
SET search_path = pg_catalog, foundation
AS $$
DECLARE
    v_link foundation.legacy_farm_links%ROWTYPE;
    v_actor_id bigint;
    v_membership_id bigint;
BEGIN
    IF coalesce(char_length(btrim(p_justification)), 0) < 10 THEN
        RAISE EXCEPTION 'rollback justification is required' USING ERRCODE='22023';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(p_idempotency_key::text, 0));
    SELECT * INTO v_link FROM foundation.legacy_farm_links
     WHERE public_id=p_link_public_id AND idempotency_key=p_idempotency_key;
    IF NOT FOUND THEN RAISE EXCEPTION 'explicit legacy mapping not found' USING ERRCODE='P0002'; END IF;
    SELECT id INTO v_actor_id FROM foundation.app_users WHERE public_id=p_actor_user_public_id AND status='active';
    IF v_actor_id IS NULL THEN RAISE EXCEPTION 'active rollback actor not found' USING ERRCODE='42501'; END IF;
    SELECT id INTO v_membership_id FROM foundation.organization_memberships
     WHERE organization_id=v_link.organization_id AND user_id=v_actor_id AND status='active'
     ORDER BY id DESC LIMIT 1;
    IF v_membership_id IS NULL THEN RAISE EXCEPTION 'rollback actor lacks active membership' USING ERRCODE='42501'; END IF;
    IF NOT p_apply THEN
        RETURN jsonb_build_object('mode','dry-run','status',v_link.status,
            'would_revoke',jsonb_build_object('legacy_links',(v_link.status='active')::integer,
                                               'farm_accesses',(v_link.status='active')::integer));
    END IF;
    IF v_link.status <> 'active' THEN RAISE EXCEPTION 'legacy mapping is not active' USING ERRCODE='55000'; END IF;

    UPDATE foundation.farm_access SET status='revoked', revoked_at=clock_timestamp(), updated_at=clock_timestamp()
     WHERE id=v_link.granted_farm_access_id AND organization_id=v_link.organization_id AND status='active';
    IF NOT FOUND THEN RAISE EXCEPTION 'mapped farm access is not active' USING ERRCODE='55000'; END IF;
    UPDATE foundation.legacy_farm_links
       SET status='revoked', revoked_at=clock_timestamp(), revoked_by=v_actor_id,
           updated_at=clock_timestamp(), justification=p_justification
     WHERE id=v_link.id;

    INSERT INTO foundation.audit_events
      (public_id,occurred_at,request_id,actor_user_id,actor_membership_id,organization_id,farm_id,
       action,entity_type,entity_public_id,result,source,metadata)
    VALUES
      (p_access_audit_public_id,clock_timestamp(),p_idempotency_key::text,v_actor_id,v_membership_id,
       v_link.organization_id,v_link.operational_farm_id,'farm.access_revoked','farm_access',NULL,
       'success','legacy_bootstrap_rollback',jsonb_build_object('reason_code','explicit_legacy_rollback','resource_type','farm_access')),
      (p_link_audit_public_id,clock_timestamp(),p_idempotency_key::text,v_actor_id,v_membership_id,
       v_link.organization_id,v_link.operational_farm_id,'legacy_farm_link.revoked','legacy_farm_link',v_link.public_id,
       'success','legacy_bootstrap_rollback',jsonb_build_object('reason_code','explicit_legacy_rollback','resource_type','legacy_farm_link'));
    RETURN jsonb_build_object('mode','apply','status','revoked','revoked',
        jsonb_build_object('legacy_links',1,'farm_accesses',1));
END;
$$;
REVOKE ALL ON FUNCTION foundation.revoke_legacy_mapping(uuid,uuid,uuid,text,uuid,uuid,boolean) FROM PUBLIC;

COMMIT;
