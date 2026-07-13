-- Vínculo explícito: somente fazenda.cliente operacional; nunca prospecção.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE TABLE foundation.legacy_farm_links (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL UNIQUE,
    source_schema text NOT NULL,
    source_table text NOT NULL,
    legacy_client_id bigint NOT NULL REFERENCES fazenda.cliente(id) ON DELETE RESTRICT CHECK (legacy_client_id > 0),
    organization_id bigint NOT NULL REFERENCES foundation.organizations(id),
    operational_farm_id bigint NOT NULL,
    granted_farm_access_id bigint NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
    mapping_version integer NOT NULL CHECK (mapping_version > 0),
    idempotency_key uuid NOT NULL UNIQUE,
    origin text NOT NULL,
    justification text NOT NULL CHECK (char_length(btrim(justification)) >= 10),
    approved_by bigint NOT NULL REFERENCES foundation.app_users(id),
    approved_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    revoked_by bigint REFERENCES foundation.app_users(id),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT legacy_farm_links_allowed_source_chk
        CHECK (source_schema = 'fazenda' AND source_table = 'cliente'),
    CONSTRAINT legacy_farm_links_origin_chk
        CHECK (origin IN ('explicit_review','explicit_synthetic_review')),
    CONSTRAINT legacy_farm_links_farm_org_fk
        FOREIGN KEY (operational_farm_id, organization_id)
        REFERENCES foundation.operational_farms(id, organization_id),
    CONSTRAINT legacy_farm_links_access_org_fk
        FOREIGN KEY (granted_farm_access_id, organization_id)
        REFERENCES foundation.farm_access(id, organization_id),
    CONSTRAINT legacy_farm_links_revocation_chk
        CHECK ((status = 'revoked') = (revoked_at IS NOT NULL)),
    CONSTRAINT legacy_farm_links_metadata_chk
        CHECK (jsonb_typeof(metadata) = 'object' AND metadata = '{}'::jsonb),
    CONSTRAINT legacy_farm_links_source_uniq
        UNIQUE (source_schema, source_table, legacy_client_id),
    CONSTRAINT legacy_farm_links_farm_uniq
        UNIQUE (operational_farm_id)
);
CREATE INDEX legacy_farm_links_org_status_idx
    ON foundation.legacy_farm_links (organization_id, status, legacy_client_id);

COMMIT;
