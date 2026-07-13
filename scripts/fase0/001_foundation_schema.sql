-- Fase 0A: estruturas novas e vazias. REVISAR e aplicar em janela controlada.
-- Não converte prospeccao.fazenda_nacional nem faz backfill do legado.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

CREATE SCHEMA foundation;
REVOKE ALL ON SCHEMA foundation FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA foundation REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA foundation REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA foundation REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

CREATE TABLE foundation.app_users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL UNIQUE,
    auth_subject text NOT NULL UNIQUE,
    display_name text,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','suspended','archived')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE foundation.organizations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL UNIQUE,
    name text NOT NULL,
    slug text NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','suspended','archived')),
    created_by bigint REFERENCES foundation.app_users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, public_id)
);

CREATE TABLE foundation.organization_memberships (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL UNIQUE,
    organization_id bigint NOT NULL REFERENCES foundation.organizations(id),
    user_id bigint NOT NULL REFERENCES foundation.app_users(id),
    role text NOT NULL CHECK (role IN ('owner','admin','manager','technician','operator','viewer')),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','revoked')),
    joined_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    revoked_at timestamptz,
    revoked_by bigint REFERENCES foundation.app_users(id),
    created_by bigint REFERENCES foundation.app_users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((status = 'revoked') = (revoked_at IS NOT NULL)),
    UNIQUE (id, organization_id)
);
CREATE UNIQUE INDEX organization_memberships_one_active_idx
    ON foundation.organization_memberships (organization_id, user_id)
    WHERE status = 'active';
CREATE INDEX organization_memberships_user_org_idx
    ON foundation.organization_memberships (user_id, organization_id, id DESC);

-- Fazenda privada operacional; deliberadamente separada da prospecção comercial.
CREATE TABLE foundation.operational_farms (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL UNIQUE,
    organization_id bigint NOT NULL REFERENCES foundation.organizations(id),
    name text NOT NULL,
    legal_name text,
    document text,
    municipality_code text,
    state char(2),
    latitude numeric(9,6),
    longitude numeric(9,6),
    area_ha numeric(14,4) CHECK (area_ha IS NULL OR area_ha >= 0),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','archived')),
    created_by bigint REFERENCES foundation.app_users(id),
    updated_by bigint REFERENCES foundation.app_users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    UNIQUE (id, organization_id)
);
CREATE INDEX operational_farms_org_status_idx ON foundation.operational_farms (organization_id, status);

CREATE TABLE foundation.farm_access (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL UNIQUE,
    organization_id bigint NOT NULL,
    farm_id bigint NOT NULL,
    membership_id bigint NOT NULL,
    access_level text NOT NULL CHECK (access_level IN ('read','operate','manage')),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','revoked')),
    expires_at timestamptz,
    revoked_at timestamptz,
    created_by bigint REFERENCES foundation.app_users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (farm_id, organization_id) REFERENCES foundation.operational_farms(id, organization_id),
    FOREIGN KEY (membership_id, organization_id) REFERENCES foundation.organization_memberships(id, organization_id),
    CHECK ((status = 'revoked') = (revoked_at IS NOT NULL)),
    UNIQUE (id, organization_id)
);
CREATE UNIQUE INDEX farm_access_one_active_idx
    ON foundation.farm_access (farm_id, membership_id)
    WHERE status = 'active';
CREATE INDEX farm_access_membership_status_idx ON foundation.farm_access (membership_id, status, farm_id);

CREATE TABLE foundation.audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL UNIQUE,
    occurred_at timestamptz NOT NULL,
    request_id text NOT NULL,
    actor_user_id bigint REFERENCES foundation.app_users(id),
    actor_membership_id bigint,
    organization_id bigint REFERENCES foundation.organizations(id),
    farm_id bigint,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_public_id uuid,
    result text NOT NULL CHECK (result IN ('success','denied','failed')),
    source text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    before_hash char(64),
    after_hash char(64),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (actor_membership_id, organization_id)
        REFERENCES foundation.organization_memberships(id, organization_id),
    FOREIGN KEY (farm_id, organization_id)
        REFERENCES foundation.operational_farms(id, organization_id),
    CHECK (char_length(request_id) BETWEEN 1 AND 200),
    CHECK (actor_membership_id IS NULL OR organization_id IS NOT NULL),
    CHECK (farm_id IS NULL OR organization_id IS NOT NULL),
    CHECK (jsonb_typeof(metadata) = 'object'),
    CHECK (NOT metadata ?| ARRAY['password','senha','token','secret','cookie','authorization','credential','full_payload']),
    CHECK (before_hash IS NULL OR before_hash ~ '^[0-9a-f]{64}$'),
    CHECK (after_hash IS NULL OR after_hash ~ '^[0-9a-f]{64}$')
);
CREATE INDEX audit_events_org_time_idx ON foundation.audit_events (organization_id, occurred_at DESC);
CREATE INDEX audit_events_request_idx ON foundation.audit_events (request_id);

CREATE TABLE foundation.units (
    code text PRIMARY KEY,
    symbol text NOT NULL,
    dimension text NOT NULL,
    description text NOT NULL,
    factor_to_base numeric NOT NULL CHECK (factor_to_base > 0),
    precision smallint NOT NULL CHECK (precision BETWEEN 0 AND 12),
    active boolean NOT NULL DEFAULT true,
    effective_from timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE foundation.technical_parameters (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL UNIQUE,
    code text NOT NULL,
    name text NOT NULL,
    description text NOT NULL,
    value_numeric numeric NOT NULL,
    unit_code text NOT NULL REFERENCES foundation.units(code),
    value_type text NOT NULL,
    origin text NOT NULL,
    source_reference text,
    scope text NOT NULL CHECK (scope IN ('global','regional','organization','farm')),
    organization_id bigint REFERENCES foundation.organizations(id),
    farm_id bigint,
    region_code text,
    animal_category text,
    valid_from timestamptz NOT NULL,
    valid_to timestamptz,
    version integer NOT NULL CHECK (version > 0),
    status text NOT NULL CHECK (status IN ('draft','published','retired')),
    created_by bigint NOT NULL REFERENCES foundation.app_users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    justification text,
    confidence numeric(5,4) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    FOREIGN KEY (farm_id, organization_id)
        REFERENCES foundation.operational_farms(id, organization_id),
    CHECK (
        (scope = 'global' AND organization_id IS NULL AND farm_id IS NULL AND region_code IS NULL)
        OR (scope = 'regional' AND organization_id IS NULL AND farm_id IS NULL AND region_code IS NOT NULL)
        OR (scope = 'organization' AND organization_id IS NOT NULL AND farm_id IS NULL AND region_code IS NULL)
        OR (scope = 'farm' AND organization_id IS NOT NULL AND farm_id IS NOT NULL AND region_code IS NULL)
    ),
    UNIQUE NULLS NOT DISTINCT (code, scope, organization_id, farm_id, region_code, animal_category, version)
);
CREATE INDEX technical_parameters_resolution_idx ON foundation.technical_parameters
    (code, farm_id, organization_id, region_code, status, valid_from DESC);

CREATE TABLE foundation.formula_definitions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL UNIQUE,
    code text NOT NULL UNIQUE,
    name text NOT NULL,
    domain text NOT NULL CHECK (domain IN ('zootecnico','agronomico','financeiro','logistico','climatico','satelite')),
    description text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE foundation.formula_versions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL UNIQUE,
    formula_id bigint NOT NULL REFERENCES foundation.formula_definitions(id),
    version integer NOT NULL CHECK (version > 0),
    implementation_id text NOT NULL,
    input_units jsonb NOT NULL,
    output_unit text NOT NULL REFERENCES foundation.units(code),
    parameter_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
    assumptions text NOT NULL,
    source_reference text,
    valid_from timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('draft','published','retired')),
    created_by bigint NOT NULL REFERENCES foundation.app_users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    checksum char(64) NOT NULL,
    technical_review text,
    confidence numeric(5,4) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    CHECK (jsonb_typeof(input_units) = 'object'),
    CHECK (jsonb_typeof(parameter_codes) = 'array'),
    CHECK (checksum ~ '^[0-9a-f]{64}$'),
    UNIQUE (formula_id, version)
);

CREATE OR REPLACE FUNCTION foundation.prevent_published_version_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = 'published' THEN
        RAISE EXCEPTION 'published version is immutable';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$;
REVOKE ALL ON FUNCTION foundation.prevent_published_version_mutation() FROM PUBLIC;

CREATE TRIGGER technical_parameter_published_immutable
BEFORE UPDATE OR DELETE ON foundation.technical_parameters
FOR EACH ROW EXECUTE FUNCTION foundation.prevent_published_version_mutation();
CREATE TRIGGER formula_version_published_immutable
BEFORE UPDATE OR DELETE ON foundation.formula_versions
FOR EACH ROW EXECUTE FUNCTION foundation.prevent_published_version_mutation();

COMMIT;
