-- migration_calibracao.sql — Brief A / Fase 2: calibração AUTO do motor.
-- Persiste a base de prenhez calibrada pelos DGs reais (shrinkage p/ o prior).
-- O motor (_prenhez_est) passa a LER esta base em vez da constante fixa —
-- a plataforma aprende sozinha com o resultado real agregado de todas as fazendas.
-- Single-row (id=1). Idempotente.
CREATE TABLE IF NOT EXISTS fazenda.calibracao_prenhez (
    id             smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    base_calibrada numeric NOT NULL,
    n              integer,
    confianca      text,
    atualizado_em  timestamptz DEFAULT now()
);
COMMENT ON TABLE fazenda.calibracao_prenhez IS
  'Brief A/F2: base de prenhez do motor, auto-calibrada pelos DGs reais (shrinkage). '
  'Lida por _prenhez_est; recalculada a cada DG. Fallback: constante PRENHEZ_BASE.';
