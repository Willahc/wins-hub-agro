-- Brief A / Fase 0 — Diagnóstico de gestação (DG): captura o RESULTADO real do cruzamento.
-- O campo `resultado` (pendente|prenhe|vazia) já existe em fazenda.cruzamento; aqui só
-- registramos QUANDO e POR QUEM o DG foi feito. Idempotente.
ALTER TABLE fazenda.cruzamento ADD COLUMN IF NOT EXISTS data_dg DATE;
ALTER TABLE fazenda.cruzamento ADD COLUMN IF NOT EXISTS dg_por  TEXT;
CREATE INDEX IF NOT EXISTS ix_cruzamento_resultado ON fazenda.cruzamento(cliente_id, resultado);
