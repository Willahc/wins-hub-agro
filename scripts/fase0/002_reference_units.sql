-- Catálogo técnico, sem parâmetros agronômicos. Executar somente após 001.
\set ON_ERROR_STOP on
BEGIN;
INSERT INTO foundation.units (code, symbol, dimension, description, factor_to_base, precision) VALUES
('kg','kg','mass','quilograma',1,3), ('t','t','mass','tonelada',1000,3),
('kg_green_mass','kg MV','green_mass','quilograma de massa verde',1,3),
('t_green_mass','t MV','green_mass','tonelada de massa verde',1000,3),
('kg_dm','kg MS','dry_matter_mass','quilograma de matéria seca',1,3),
('t_dm','t MS','dry_matter_mass','tonelada de matéria seca',1000,3),
('m2','m²','area','metro quadrado',1,3), ('ha','ha','area','hectare',10000,4),
('m3','m³','volume','metro cúbico',1,3), ('l','L','liquid_volume','litro',1,3),
('animal','animal','count_animal','animal',1,0), ('head','cab','count_animal','cabeça',1,0),
('day','dia','time','dia',1,2), ('percent','%','ratio','percentual',0.01,4),
('fraction','fração','ratio','fração decimal',1,6), ('celsius','°C','temperature','grau Celsius',1,2),
('percent_moisture','% umid.','ratio','percentual de umidade',0.01,3),
('brl','R$','money','real brasileiro',1,2),
('kg_dm_per_animal_day','kg MS/animal/dia','dry_matter_per_animal_day','matéria seca por animal por dia',1,3),
('kg_dm_per_ha','kg MS/ha','dry_matter_per_area','matéria seca por hectare',1,3),
('t_per_ha','t/ha','mass_per_area','tonelada por hectare',1000,3),
('brl_per_t','R$/t','money_per_mass','reais por tonelada',1,2),
('brl_per_animal','R$/animal','money_per_animal','reais por animal',1,2)
ON CONFLICT (code) DO NOTHING;

CREATE OR REPLACE FUNCTION foundation.assert_compatible_units(source_code text, target_code text)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = pg_catalog, foundation
AS $$
DECLARE
    source_dimension text;
    target_dimension text;
BEGIN
    SELECT dimension INTO STRICT source_dimension FROM foundation.units WHERE code = source_code;
    SELECT dimension INTO STRICT target_dimension FROM foundation.units WHERE code = target_code;
    IF source_dimension <> target_dimension THEN
        RAISE EXCEPTION 'incompatible unit dimensions' USING ERRCODE = '22023';
    END IF;
    RETURN true;
END;
$$;
REVOKE ALL ON FUNCTION foundation.assert_compatible_units(text, text) FROM PUBLIC;
COMMIT;
