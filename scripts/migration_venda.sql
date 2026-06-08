-- Feature 4: registro de vendas de genética (doses/embriões/animais) por município.
-- Mari lança no App (offline/outbox); admin Monte Sião vê/edita no Hub. Idempotente.
CREATE TABLE IF NOT EXISTS fazenda.venda (
  id             SERIAL PRIMARY KEY,
  uuid           TEXT UNIQUE,                  -- idempotência p/ replay do outbox
  cliente_id     INTEGER REFERENCES fazenda.cliente(id),
  municipio      TEXT,
  uf             CHAR(2),
  touro_id       INTEGER,                      -- mercado.reprodutor (touro vendido)
  touro_nome     TEXT,
  data_venda     DATE DEFAULT current_date,
  tipo           TEXT DEFAULT 'semen',         -- semen | embriao | animal
  quantidade     INTEGER DEFAULT 1,
  valor_unitario NUMERIC(12,2),
  roi_estimado   NUMERIC(12,2),
  registrado_por TEXT DEFAULT 'mari',          -- mari | admin
  coletado_em    TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_venda_municipio ON fazenda.venda(uf, municipio);
CREATE INDEX IF NOT EXISTS ix_venda_touro     ON fazenda.venda(touro_id);
CREATE INDEX IF NOT EXISTS ix_venda_data      ON fazenda.venda(data_venda);
