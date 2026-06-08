-- Brief A/F1: liga o bezerro ao cruzamento que o gerou (fecha o loop de aprendizado/peso).
ALTER TABLE fazenda.animal ADD COLUMN IF NOT EXISTS cruzamento_id INTEGER;
CREATE INDEX IF NOT EXISTS ix_animal_cruzamento ON fazenda.animal(cruzamento_id);
