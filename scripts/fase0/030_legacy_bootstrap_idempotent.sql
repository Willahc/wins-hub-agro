-- Função invoker para dry-run/apply explícito de um mapping revisado.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE FUNCTION foundation.process_legacy_mapping(p_mapping jsonb, p_apply boolean DEFAULT false)
RETURNS jsonb
LANGUAGE plpgsql
VOLATILE
SECURITY INVOKER
SET search_path = pg_catalog, foundation
AS $$
DECLARE
    v_user_uuid uuid;
    v_org_uuid uuid;
    v_membership_uuid uuid;
    v_farm_uuid uuid;
    v_access_uuid uuid;
    v_link_uuid uuid;
    v_idempotency_key uuid;
    v_approved_by_uuid uuid;
    v_approved_at timestamptz;
    v_legacy_id bigint;
    v_mapping_version integer;
    v_user_id bigint;
    v_org_id bigint;
    v_membership_id bigint;
    v_farm_id bigint;
    v_access_id bigint;
    v_link_id bigint;
    v_approver_id bigint;
    v_existing_uuid uuid;
    v_existing_text text;
    v_existing_text2 text;
    v_existing_org bigint;
    v_existing_farm bigint;
    v_existing_user bigint;
    v_existing_idempotency uuid;
    v_existing_version integer;
    v_existing_status text;
    v_conflicts text[] := ARRAY[]::text[];
    v_created_user boolean := false;
    v_created_org boolean := false;
    v_created_membership boolean := false;
    v_created_farm boolean := false;
    v_created_access boolean := false;
    v_created_link boolean := false;
    v_audit_ids jsonb;
    v_report jsonb;
BEGIN
    IF jsonb_typeof(p_mapping) <> 'object' THEN
        RAISE EXCEPTION 'mapping must be a JSON object' USING ERRCODE = '22023';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM jsonb_array_elements_text('["user_public_id","auth_subject","display_name",
            "organization_public_id","organization_name","organization_slug","membership_public_id",
            "role","farm_public_id","farm_name","access_public_id","access_level","link_public_id",
            "idempotency_key","source_schema","source_table","legacy_client_id","mapping_version",
            "origin","justification","approved_by_user_public_id","approved_at"]'::jsonb) required(key)
         WHERE nullif(btrim(p_mapping->>required.key), '') IS NULL
    ) THEN
        RAISE EXCEPTION 'mapping has missing required fields' USING ERRCODE = '22023';
    END IF;
    IF p_mapping->>'source_schema' IS DISTINCT FROM 'fazenda'
       OR p_mapping->>'source_table' IS DISTINCT FROM 'cliente' THEN
        RAISE EXCEPTION 'legacy source is not allowed' USING ERRCODE = '22023';
    END IF;
    IF coalesce(char_length(btrim(p_mapping->>'justification')), 0) < 10 THEN
        RAISE EXCEPTION 'justification is required' USING ERRCODE = '22023';
    END IF;
    IF p_mapping->>'role' NOT IN ('owner','admin','manager','technician','operator','viewer') THEN
        RAISE EXCEPTION 'invalid membership role' USING ERRCODE = '22023';
    END IF;
    IF p_mapping->>'access_level' NOT IN ('read','operate','manage') THEN
        RAISE EXCEPTION 'invalid farm access level' USING ERRCODE = '22023';
    END IF;

    BEGIN
        v_user_uuid := (p_mapping->>'user_public_id')::uuid;
        v_org_uuid := (p_mapping->>'organization_public_id')::uuid;
        v_membership_uuid := (p_mapping->>'membership_public_id')::uuid;
        v_farm_uuid := (p_mapping->>'farm_public_id')::uuid;
        v_access_uuid := (p_mapping->>'access_public_id')::uuid;
        v_link_uuid := (p_mapping->>'link_public_id')::uuid;
        v_idempotency_key := (p_mapping->>'idempotency_key')::uuid;
        v_approved_by_uuid := (p_mapping->>'approved_by_user_public_id')::uuid;
        v_approved_at := (p_mapping->>'approved_at')::timestamptz;
        v_legacy_id := (p_mapping->>'legacy_client_id')::bigint;
        v_mapping_version := (p_mapping->>'mapping_version')::integer;
    EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range THEN
        RAISE EXCEPTION 'invalid UUID, timestamp, legacy_client_id or mapping_version' USING ERRCODE = '22023';
    END;
    IF v_legacy_id <= 0 OR v_mapping_version <= 0 THEN
        RAISE EXCEPTION 'legacy_client_id and mapping_version must be positive' USING ERRCODE = '22023';
    END IF;
    IF p_mapping->>'origin' NOT IN ('explicit_review','explicit_synthetic_review') THEN
        RAISE EXCEPTION 'mapping origin is not allowed' USING ERRCODE = '22023';
    END IF;
    IF v_approved_at > clock_timestamp() + interval '5 minutes' THEN
        RAISE EXCEPTION 'approval timestamp cannot be in the future' USING ERRCODE = '22023';
    END IF;
    IF coalesce(char_length(btrim(p_mapping->>'auth_subject')), 0) < 3
       OR coalesce(char_length(btrim(p_mapping->>'organization_name')), 0) < 3
       OR coalesce(char_length(btrim(p_mapping->>'organization_slug')), 0) < 3
       OR coalesce(char_length(btrim(p_mapping->>'farm_name')), 0) < 3 THEN
        RAISE EXCEPTION 'required identity and destination names are invalid' USING ERRCODE = '22023';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended(v_idempotency_key::text, 0));

    SELECT id, public_id, auth_subject INTO v_user_id, v_existing_uuid, v_existing_text
      FROM foundation.app_users
     WHERE public_id = v_user_uuid OR auth_subject = p_mapping->>'auth_subject'
     ORDER BY (public_id = v_user_uuid) DESC LIMIT 1;
    IF FOUND AND (v_existing_uuid <> v_user_uuid OR v_existing_text <> p_mapping->>'auth_subject') THEN
        v_conflicts := array_append(v_conflicts, 'user_identity_conflict');
    END IF;

    SELECT id INTO v_approver_id FROM foundation.app_users WHERE public_id = v_approved_by_uuid;
    IF v_approver_id IS NULL AND v_approved_by_uuid <> v_user_uuid THEN
        v_conflicts := array_append(v_conflicts, 'approver_missing');
    END IF;

    SELECT id, public_id, slug, name INTO v_org_id, v_existing_uuid, v_existing_text, v_existing_text2
      FROM foundation.organizations
     WHERE public_id = v_org_uuid OR slug = p_mapping->>'organization_slug'
     ORDER BY (public_id = v_org_uuid) DESC LIMIT 1;
    IF FOUND AND (v_existing_uuid <> v_org_uuid OR v_existing_text <> p_mapping->>'organization_slug'
        OR v_existing_text2 <> p_mapping->>'organization_name') THEN
        v_conflicts := array_append(v_conflicts, 'organization_identity_conflict');
    END IF;

    IF v_user_id IS NOT NULL AND v_org_id IS NOT NULL THEN
        SELECT id, public_id, role, organization_id, user_id, status
          INTO v_membership_id, v_existing_uuid, v_existing_text, v_existing_org, v_existing_user, v_existing_status
          FROM foundation.organization_memberships
         WHERE public_id = v_membership_uuid OR (organization_id = v_org_id AND user_id = v_user_id)
         ORDER BY (public_id = v_membership_uuid) DESC, id DESC LIMIT 1;
        IF FOUND AND (v_existing_uuid <> v_membership_uuid OR v_existing_text <> p_mapping->>'role'
            OR v_existing_org <> v_org_id OR v_existing_user <> v_user_id OR v_existing_status <> 'active') THEN
            v_conflicts := array_append(v_conflicts, 'membership_role_or_scope_conflict');
        END IF;
    ELSE
        SELECT id INTO v_membership_id FROM foundation.organization_memberships WHERE public_id = v_membership_uuid;
        IF FOUND THEN v_conflicts := array_append(v_conflicts, 'membership_parent_conflict'); END IF;
    END IF;

    SELECT id, public_id, organization_id, name, status
      INTO v_farm_id, v_existing_uuid, v_existing_org, v_existing_text, v_existing_status
      FROM foundation.operational_farms
     WHERE public_id = v_farm_uuid LIMIT 1;
    IF FOUND AND (v_existing_uuid <> v_farm_uuid OR v_org_id IS NULL OR v_existing_org <> v_org_id
        OR v_existing_text <> p_mapping->>'farm_name' OR v_existing_status <> 'active') THEN
        v_conflicts := array_append(v_conflicts, 'farm_organization_conflict');
    END IF;

    IF v_membership_id IS NOT NULL AND v_farm_id IS NOT NULL THEN
        SELECT id, public_id, access_level, organization_id, status
          INTO v_access_id, v_existing_uuid, v_existing_text, v_existing_org, v_existing_status
          FROM foundation.farm_access
         WHERE public_id = v_access_uuid OR (farm_id = v_farm_id AND membership_id = v_membership_id)
         ORDER BY (public_id = v_access_uuid) DESC, id DESC LIMIT 1;
        IF FOUND AND (v_existing_uuid <> v_access_uuid OR v_existing_text <> p_mapping->>'access_level'
            OR v_existing_org <> v_org_id OR v_existing_status <> 'active') THEN
            v_conflicts := array_append(v_conflicts, 'farm_access_conflict');
        END IF;
    END IF;

    SELECT id, public_id, organization_id, operational_farm_id, idempotency_key, mapping_version, status
      INTO v_link_id, v_existing_uuid, v_existing_org, v_existing_farm, v_existing_idempotency, v_existing_version,
           v_existing_status
      FROM foundation.legacy_farm_links
     WHERE public_id = v_link_uuid
        OR (source_schema = 'fazenda' AND source_table = 'cliente' AND legacy_client_id = v_legacy_id)
        OR operational_farm_id = v_farm_id
     ORDER BY (public_id = v_link_uuid) DESC, id DESC LIMIT 1;
    IF FOUND AND (v_existing_uuid <> v_link_uuid OR v_org_id IS NULL OR v_existing_org <> v_org_id
        OR v_farm_id IS NULL OR v_existing_farm <> v_farm_id
        OR v_existing_idempotency <> v_idempotency_key OR v_existing_version <> v_mapping_version
        OR v_existing_status <> 'active') THEN
        v_conflicts := array_append(v_conflicts, 'legacy_link_conflict');
    END IF;

    v_report := jsonb_build_object(
        'mode', CASE WHEN p_apply THEN 'apply' ELSE 'dry-run' END,
        'status', CASE WHEN cardinality(v_conflicts) = 0 THEN 'ready' ELSE 'blocked' END,
        'would_create', jsonb_build_object(
            'users', (v_user_id IS NULL)::integer,
            'organizations', (v_org_id IS NULL)::integer,
            'memberships', (v_membership_id IS NULL)::integer,
            'farms', (v_farm_id IS NULL)::integer,
            'farm_accesses', (v_access_id IS NULL)::integer,
            'legacy_links', (v_link_id IS NULL)::integer
        ),
        'existing', jsonb_build_object(
            'users', (v_user_id IS NOT NULL)::integer,
            'organizations', (v_org_id IS NOT NULL)::integer,
            'memberships', (v_membership_id IS NOT NULL)::integer,
            'farms', (v_farm_id IS NOT NULL)::integer,
            'farm_accesses', (v_access_id IS NOT NULL)::integer,
            'legacy_links', (v_link_id IS NOT NULL)::integer
        ),
        'conflicts', to_jsonb(v_conflicts),
        'blocked_actions', CASE WHEN cardinality(v_conflicts) > 0
            THEN jsonb_build_array('apply') ELSE '[]'::jsonb END,
        'idempotency_key', v_idempotency_key
    );
    IF NOT p_apply THEN RETURN v_report; END IF;
    IF cardinality(v_conflicts) > 0 THEN
        RAISE EXCEPTION 'legacy mapping conflict: %', array_to_string(v_conflicts, ',') USING ERRCODE = '23505';
    END IF;
    IF jsonb_typeof(p_mapping->'audit_public_ids') <> 'object'
       OR EXISTS (
           SELECT 1 FROM jsonb_array_elements_text('["user","organization","membership","farm","access","link"]'::jsonb) required(key)
            WHERE nullif(p_mapping->'audit_public_ids'->>required.key, '') IS NULL
       ) THEN
        RAISE EXCEPTION 'audit_public_ids is required for apply' USING ERRCODE = '22023';
    END IF;
    v_audit_ids := p_mapping->'audit_public_ids';

    IF v_user_id IS NULL THEN
        INSERT INTO foundation.app_users (public_id, auth_subject, display_name)
        VALUES (v_user_uuid, p_mapping->>'auth_subject', p_mapping->>'display_name') RETURNING id INTO v_user_id;
        v_created_user := true;
    END IF;
    IF v_approver_id IS NULL AND v_approved_by_uuid = v_user_uuid THEN v_approver_id := v_user_id; END IF;
    IF v_org_id IS NULL THEN
        INSERT INTO foundation.organizations (public_id, name, slug, created_by)
        VALUES (v_org_uuid, p_mapping->>'organization_name', p_mapping->>'organization_slug', v_approver_id)
        RETURNING id INTO v_org_id;
        v_created_org := true;
    END IF;
    IF v_membership_id IS NULL THEN
        INSERT INTO foundation.organization_memberships
            (public_id, organization_id, user_id, role, status, created_by)
        VALUES (v_membership_uuid, v_org_id, v_user_id, p_mapping->>'role', 'active', v_approver_id)
        RETURNING id INTO v_membership_id;
        v_created_membership := true;
    END IF;
    IF v_farm_id IS NULL THEN
        INSERT INTO foundation.operational_farms (public_id, organization_id, name, created_by)
        VALUES (v_farm_uuid, v_org_id, p_mapping->>'farm_name', v_approver_id) RETURNING id INTO v_farm_id;
        v_created_farm := true;
    END IF;
    IF v_access_id IS NULL THEN
        INSERT INTO foundation.farm_access
            (public_id, organization_id, farm_id, membership_id, access_level, status, created_by)
        VALUES (v_access_uuid, v_org_id, v_farm_id, v_membership_id,
                p_mapping->>'access_level', 'active', v_approver_id) RETURNING id INTO v_access_id;
        v_created_access := true;
    END IF;
    IF v_link_id IS NULL THEN
        INSERT INTO foundation.legacy_farm_links
            (public_id, source_schema, source_table, legacy_client_id, organization_id,
             operational_farm_id, granted_farm_access_id, mapping_version, idempotency_key, origin, justification,
             approved_by, approved_at)
        VALUES (v_link_uuid, 'fazenda', 'cliente', v_legacy_id, v_org_id, v_farm_id, v_access_id,
                v_mapping_version, v_idempotency_key, p_mapping->>'origin',
                p_mapping->>'justification', v_approver_id, v_approved_at)
        RETURNING id INTO v_link_id;
        v_created_link := true;
    END IF;

    INSERT INTO foundation.audit_events
        (public_id, occurred_at, request_id, actor_user_id, actor_membership_id,
         organization_id, farm_id, action, entity_type, entity_public_id, result, source, metadata)
    SELECT (v_audit_ids->>event_key)::uuid, clock_timestamp(), v_idempotency_key::text,
           v_approver_id, v_membership_id, v_org_id,
           CASE WHEN event_key IN ('farm','access','link') THEN v_farm_id ELSE NULL END,
           action, entity_type, entity_uuid, 'success', 'legacy_bootstrap',
           jsonb_build_object('reason_code','explicit_legacy_mapping','resource_type',entity_type)
      FROM (VALUES
          ('user', 'user.created', 'app_user', v_user_uuid, v_created_user),
          ('organization', 'organization.created', 'organization', v_org_uuid, v_created_org),
          ('membership', 'membership.created', 'organization_membership', v_membership_uuid, v_created_membership),
          ('farm', 'farm.created', 'operational_farm', v_farm_uuid, v_created_farm),
          ('access', 'farm.access_granted', 'farm_access', v_access_uuid, v_created_access),
          ('link', 'legacy_farm_link.created', 'legacy_farm_link', v_link_uuid, v_created_link)
      ) AS events(event_key, action, entity_type, entity_uuid, was_created)
     WHERE was_created;

    RETURN v_report || jsonb_build_object('status','applied','created',jsonb_build_object(
        'users', v_created_user::integer, 'organizations', v_created_org::integer,
        'memberships', v_created_membership::integer, 'farms', v_created_farm::integer,
        'farm_accesses', v_created_access::integer, 'legacy_links', v_created_link::integer));
END;
$$;
REVOKE ALL ON FUNCTION foundation.process_legacy_mapping(jsonb, boolean) FROM PUBLIC;

COMMIT;
