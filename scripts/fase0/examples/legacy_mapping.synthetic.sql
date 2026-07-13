-- Exemplo seguro: apenas dry-run. Apply exige chamada explícita com segundo argumento true.
\set ON_ERROR_STOP on
SELECT foundation.process_legacy_mapping(
    :'mapping_json'::jsonb,
    false
);
