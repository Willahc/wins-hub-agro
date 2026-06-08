-- Brief B / Fase 0 — Estação de monta (IATF em lote).
-- A estação é o container da temporada; a IATF em lote gera N cruzamentos (1 por matriz)
-- de uma vez, alimentando o flywheel (Brief A) em escala. Idempotente.
CREATE TABLE IF NOT EXISTS fazenda.estacao_monta (
  id           SERIAL PRIMARY KEY,
  uuid         TEXT UNIQUE,
  cliente_id   INTEGER REFERENCES fazenda.cliente(id),
  nome         TEXT,
  tipo         TEXT DEFAULT 'iatf',          -- iatf | monta_natural | repasse
  protocolo    TEXT,
  data_inicio  DATE DEFAULT current_date,
  data_fim     DATE,
  status       TEXT DEFAULT 'ativa',         -- planejada | ativa | encerrada
  coletado_em  TIMESTAMP DEFAULT now()
);
-- liga o cruzamento à estação que o gerou (estacao_monta TEXT já existe = rótulo do semestre)
ALTER TABLE fazenda.cruzamento ADD COLUMN IF NOT EXISTS estacao_id INTEGER;
CREATE INDEX IF NOT EXISTS ix_estacao_cliente       ON fazenda.estacao_monta(cliente_id);
CREATE INDEX IF NOT EXISTS ix_cruzamento_estacao_id ON fazenda.cruzamento(estacao_id);
