-- Brief B/F1: liga os passos do protocolo (eventos de agenda do lote) à estação de monta.
ALTER TABLE fazenda.evento_sanitario ADD COLUMN IF NOT EXISTS estacao_id INTEGER;
CREATE INDEX IF NOT EXISTS ix_evsan_estacao ON fazenda.evento_sanitario(estacao_id);
