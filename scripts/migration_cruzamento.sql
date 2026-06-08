-- Feature 2/6: registro de cruzamentos (acasalamentos efetivados no campo).
-- Sustenta o fluxo de 3 toques (F2) e o gráfico de evolução genética (F6).
-- Idempotente: pode rodar várias vezes.
CREATE TABLE IF NOT EXISTS fazenda.cruzamento (
  id              SERIAL PRIMARY KEY,
  uuid            TEXT UNIQUE,                 -- idempotência p/ replay do outbox offline
  cliente_id      INTEGER REFERENCES fazenda.cliente(id),
  vaca_id         INTEGER,                     -- fazenda.animal.id (a matriz)
  vaca_espelho_id INTEGER,                     -- mercado.reprodutor (espelho da vaca, p/ genética)
  touro_id        INTEGER,                     -- mercado.reprodutor (touro do catálogo)
  touro_nome      TEXT,
  data_cruzamento DATE DEFAULT current_date,
  estacao_monta   TEXT,                        -- 'AAAA-1' / 'AAAA-2' (semestre)
  ganho_cria      NUMERIC(10,2),               -- snapshot do R$/cria no momento (F1)
  prog_iqgg       NUMERIC(10,2),               -- snapshot do IQGg projetado da cria
  prenhez_est     INTEGER,                     -- snapshot da prenhez estimada % (F3)
  resultado       TEXT DEFAULT 'pendente',     -- pendente | prenhe | vazia
  registrado_por  TEXT,
  coletado_em     TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_cruzamento_cliente ON fazenda.cruzamento(cliente_id);
CREATE INDEX IF NOT EXISTS ix_cruzamento_estacao ON fazenda.cruzamento(cliente_id, estacao_monta);
CREATE INDEX IF NOT EXISTS ix_cruzamento_vaca    ON fazenda.cruzamento(vaca_id);
