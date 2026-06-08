-- build_fazenda_campo.sql
-- Migração fundacional do APP DE CAMPO + FAZENDA CONECTADA.
-- Tudo ADITIVO e reversível: nenhuma coluna/tabela existente é alterada de forma destrutiva.
-- Premissa: fazenda.* hoje tem 0 linhas (schema pronto, sem dados) — risco de aplicação é mínimo.
--
-- O que adiciona:
--   1. fazenda.grupo_manejo   -> grupo de contemporâneos / lote (pré-requisito de índice E genética)
--   2. fazenda.animal         -> coluna eid (RFID eletrônico) + grupo_id (lote atual)
--   3. fazenda.medicao        -> origem / dispositivo / medido_em / uuid / grupo_id (sensor-aware, idempotente)
--   4. fazenda.evento_sanitario -> vacina/vermífugo/medicamento + calendário (proxima_dose)
--   5. fazenda.movimentacao (+ _animal) -> rastreabilidade SISBOV/GTA (lote E individual)
--   6. fazenda.leitura_sensor -> telemetria bruta (append-only, particionada por mês, idempotente)
--   7. fazenda.v_sensor_peso_diario -> view de rollup (stream bruto -> peso diário p/ medicao)
--
-- Reversão completa no bloco comentado ao final.
BEGIN;

-- =====================================================================
-- 1) GRUPO DE CONTEMPORÂNEOS / LOTE
--    Sem isso, GMD e taxa de prenhez não comparam nada (mesmo manejo,
--    mesma idade, mesmo pasto). É o pré-requisito do fosso genético.
-- =====================================================================
CREATE TABLE IF NOT EXISTS fazenda.grupo_manejo (
  id              serial PRIMARY KEY,
  cliente_id      integer NOT NULL REFERENCES fazenda.cliente(id),
  nome            varchar(120) NOT NULL,
  tipo            varchar(30),                 -- contemporaneo | lote_manejo | piquete | safra
  especie_codigo  varchar(3) NOT NULL DEFAULT 'BOV' REFERENCES catalogo.especie(codigo),
  data_inicio     date,
  data_fim        date,
  obs             text,
  criado_em       timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_grupo_cliente ON fazenda.grupo_manejo (cliente_id);

-- =====================================================================
-- 2) ANIMAL: identidade eletrônica + lote atual
--    eid = RFID ISO 11784/11785 (15 dígitos); é OUTRO identificador,
--    distinto do brinco visual (que cai / é trocado). Chave de junção
--    da telemetria; o brinco continua sendo rótulo humano.
-- =====================================================================
ALTER TABLE fazenda.animal ADD COLUMN IF NOT EXISTS eid      varchar(32);
ALTER TABLE fazenda.animal ADD COLUMN IF NOT EXISTS grupo_id integer REFERENCES fazenda.grupo_manejo(id);
ALTER TABLE fazenda.animal ADD COLUMN IF NOT EXISTS uuid     uuid;                 -- idempotência do outbox de campo
ALTER TABLE fazenda.animal ADD COLUMN IF NOT EXISTS reprodutor_espelho_id integer  -- espelho no catálogo (acasalamento)
  REFERENCES mercado.reprodutor(id);
-- ciclo de vida do animal: descarte (cull) e marcação de doadora (FIV/TE)
ALTER TABLE fazenda.animal ADD COLUMN IF NOT EXISTS eh_doadora      boolean DEFAULT false;
ALTER TABLE fazenda.animal ADD COLUMN IF NOT EXISTS motivo_descarte varchar(120);
ALTER TABLE fazenda.animal ADD COLUMN IF NOT EXISTS data_saida      date;
CREATE UNIQUE INDEX IF NOT EXISTS idx_animal_eid
  ON fazenda.animal (cliente_id, eid) WHERE eid IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_animal_uuid
  ON fazenda.animal (uuid) WHERE uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_animal_grupo ON fazenda.animal (grupo_id);

-- =====================================================================
-- 3) MEDICAO: sensor-aware, idempotente, com grupo de contemporâneos
--    data_medicao (date) CONTINUA sendo a verdade p/ genética; medido_em
--    (timestamptz) acrescenta hora p/ correlação (estresse térmico etc.).
--    origem distingue manual x balança x sensor; uuid deduplica ingestão.
-- =====================================================================
ALTER TABLE fazenda.medicao ADD COLUMN IF NOT EXISTS origem      varchar(16) DEFAULT 'manual'; -- manual|balanca|sensor|estimado
ALTER TABLE fazenda.medicao ADD COLUMN IF NOT EXISTS dispositivo varchar(64);
ALTER TABLE fazenda.medicao ADD COLUMN IF NOT EXISTS medido_em   timestamptz;
ALTER TABLE fazenda.medicao ADD COLUMN IF NOT EXISTS uuid        uuid;
ALTER TABLE fazenda.medicao ADD COLUMN IF NOT EXISTS grupo_id    integer REFERENCES fazenda.grupo_manejo(id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_medicao_uuid ON fazenda.medicao (uuid) WHERE uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_medicao_grupo ON fazenda.medicao (grupo_id);

-- =====================================================================
-- 4) SANITÁRIO: vacina / vermífugo / medicamento + calendário
--    Aplicação individual (animal_id) OU em lote (grupo_id). proxima_dose
--    alimenta os alertas (push / WhatsApp). uuid p/ idempotência de campo.
-- =====================================================================
CREATE TABLE IF NOT EXISTS fazenda.evento_sanitario (
  id            serial PRIMARY KEY,
  animal_id     integer REFERENCES fazenda.animal(id) ON DELETE CASCADE,
  grupo_id      integer REFERENCES fazenda.grupo_manejo(id),
  tipo          varchar(30) NOT NULL,          -- vacina | vermifugo | medicamento | exame | outro
  produto       varchar(150),
  data_evento   date NOT NULL,
  proxima_dose  date,                          -- p/ calendário e lembretes
  dose          varchar(40),
  via           varchar(30),                   -- IM | SC | oral | tópica...
  responsavel   varchar(120),
  obs           text,
  uuid          uuid,
  registrado_em timestamptz DEFAULT now(),
  lembrete_concluido    boolean DEFAULT false,   -- proxima_dose já cumprida/dispensada (sai da agenda)
  lembrete_concluido_em timestamptz,
  CONSTRAINT evento_sanitario_alvo_chk CHECK (animal_id IS NOT NULL OR grupo_id IS NOT NULL)
);
-- evolução idempotente (tabela pode já existir sem as colunas de lembrete)
ALTER TABLE fazenda.evento_sanitario ADD COLUMN IF NOT EXISTS lembrete_concluido    boolean DEFAULT false;
ALTER TABLE fazenda.evento_sanitario ADD COLUMN IF NOT EXISTS lembrete_concluido_em timestamptz;
CREATE INDEX IF NOT EXISTS idx_sanit_animal_data ON fazenda.evento_sanitario (animal_id, data_evento);
CREATE INDEX IF NOT EXISTS idx_sanit_grupo       ON fazenda.evento_sanitario (grupo_id);
CREATE INDEX IF NOT EXISTS idx_sanit_proxima     ON fazenda.evento_sanitario (proxima_dose) WHERE proxima_dose IS NOT NULL;
-- agenda: lembretes pendentes (proxima_dose definida e ainda não cumprida)
CREATE INDEX IF NOT EXISTS idx_sanit_agenda      ON fazenda.evento_sanitario (proxima_dose) WHERE proxima_dose IS NOT NULL AND lembrete_concluido = false;
CREATE UNIQUE INDEX IF NOT EXISTS idx_sanit_uuid  ON fazenda.evento_sanitario (uuid) WHERE uuid IS NOT NULL;

-- =====================================================================
-- 5) RASTREABILIDADE SISBOV / GTA (movimentação)
--    Cabeçalho por evento (com nº de GTA, origem/destino) + vínculo
--    individual opcional (SISBOV exige identificação individual).
-- =====================================================================
CREATE TABLE IF NOT EXISTS fazenda.movimentacao (
  id            serial PRIMARY KEY,
  cliente_id    integer NOT NULL REFERENCES fazenda.cliente(id),
  tipo          varchar(20) NOT NULL,          -- entrada | saida | transferencia | nascimento | morte | abate
  data_evento   date NOT NULL,
  gta_numero    varchar(30),
  origem        varchar(200),
  destino       varchar(200),
  finalidade    varchar(60),                   -- reproducao | engorda | abate | leilao...
  quantidade    integer,
  obs           text,
  registrado_em timestamptz DEFAULT now()
);
-- uuid p/ idempotência da captura offline (igual medicao/evento_sanitario)
ALTER TABLE fazenda.movimentacao ADD COLUMN IF NOT EXISTS uuid uuid;
CREATE INDEX IF NOT EXISTS idx_mov_cliente_data ON fazenda.movimentacao (cliente_id, data_evento);
CREATE INDEX IF NOT EXISTS idx_mov_gta          ON fazenda.movimentacao (gta_numero) WHERE gta_numero IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_mov_uuid   ON fazenda.movimentacao (uuid) WHERE uuid IS NOT NULL;

CREATE TABLE IF NOT EXISTS fazenda.movimentacao_animal (
  movimentacao_id integer NOT NULL REFERENCES fazenda.movimentacao(id) ON DELETE CASCADE,
  animal_id       integer NOT NULL REFERENCES fazenda.animal(id),
  PRIMARY KEY (movimentacao_id, animal_id)
);

-- =====================================================================
-- 6) TELEMETRIA BRUTA (firehose) — append-only, particionada por mês
--    NÃO é a medicao: aqui entra o stream cru (balança de passagem,
--    acelerômetro, bolus, cocho). meta (jsonb) guarda o payload integral
--    p/ não perder nada. Postgres 16 nativo (sem TimescaleDB): partição
--    por mês + BRIN aguentam até o sensor de cio entrar em volume.
--    OBS: índice UNIQUE em tabela particionada precisa conter a chave de
--    partição -> dedupe por (dispositivo, uuid, medido_em).
-- =====================================================================
CREATE TABLE IF NOT EXISTS fazenda.leitura_sensor (
  id          bigint GENERATED ALWAYS AS IDENTITY,
  animal_id   integer REFERENCES fazenda.animal(id),
  cliente_id  integer REFERENCES fazenda.cliente(id),
  dispositivo varchar(64) NOT NULL,
  tipo        varchar(24) NOT NULL,            -- peso | temp | atividade | ph | consumo | ndvi...
  medido_em   timestamptz NOT NULL,
  valor       numeric(12,4),
  meta        jsonb,
  uuid        uuid NOT NULL,
  ingerido_em timestamptz DEFAULT now(),
  PRIMARY KEY (id, medido_em)
) PARTITION BY RANGE (medido_em);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sensor_dedupe
  ON fazenda.leitura_sensor (dispositivo, uuid, medido_em);
CREATE INDEX IF NOT EXISTS idx_sensor_brin
  ON fazenda.leitura_sensor USING brin (medido_em);
CREATE INDEX IF NOT EXISTS idx_sensor_animal
  ON fazenda.leitura_sensor (animal_id, tipo, medido_em);

-- Partições mensais: mês corrente + 12 meses à frente. Em produção,
-- automatize a criação contínua (cron ou pg_partman).
DO $$
DECLARE d date := date_trunc('month', now())::date; e date; i int;
BEGIN
  FOR i IN 0..12 LOOP
    e := (d + interval '1 month')::date;
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS fazenda.leitura_sensor_%s PARTITION OF fazenda.leitura_sensor FOR VALUES FROM (%L) TO (%L)',
      to_char(d, 'YYYYMM'), d, e);
    d := e;
  END LOOP;
END $$;
-- Rede de segurança p/ leituras fora da janela (ex.: backfill antigo).
CREATE TABLE IF NOT EXISTS fazenda.leitura_sensor_default
  PARTITION OF fazenda.leitura_sensor DEFAULT;

-- =====================================================================
-- 7) ROLLUP: stream bruto -> peso diário (alimenta fazenda.medicao)
--    Mediana das pesagens válidas do dia, descartando outlier de balança
--    suja. Um job diário materializa isto em medicao (origem='sensor').
-- =====================================================================
DROP VIEW IF EXISTS fazenda.v_sensor_peso_diario;
CREATE VIEW fazenda.v_sensor_peso_diario AS
SELECT
  animal_id,
  (medido_em AT TIME ZONE 'America/Sao_Paulo')::date AS dia,
  COUNT(*)                                           AS n_leituras,
  ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY valor)::numeric, 2) AS peso_kg_mediana,
  MIN(dispositivo)                                   AS dispositivo
FROM   fazenda.leitura_sensor
WHERE  tipo = 'peso' AND valor IS NOT NULL AND animal_id IS NOT NULL
GROUP  BY animal_id, (medido_em AT TIME ZONE 'America/Sao_Paulo')::date;

COMMIT;

-- =====================================================================
-- REVERTER (rodar manualmente, na ordem; respeita dependências/FKs):
-- BEGIN;
--   DROP VIEW  IF EXISTS fazenda.v_sensor_peso_diario;
--   DROP TABLE IF EXISTS fazenda.leitura_sensor CASCADE;   -- remove todas as partições
--   DROP TABLE IF EXISTS fazenda.movimentacao_animal;
--   DROP TABLE IF EXISTS fazenda.movimentacao;
--   DROP TABLE IF EXISTS fazenda.evento_sanitario;
--   ALTER TABLE fazenda.medicao DROP COLUMN IF EXISTS grupo_id;
--   ALTER TABLE fazenda.medicao DROP COLUMN IF EXISTS uuid;
--   ALTER TABLE fazenda.medicao DROP COLUMN IF EXISTS medido_em;
--   ALTER TABLE fazenda.medicao DROP COLUMN IF EXISTS dispositivo;
--   ALTER TABLE fazenda.medicao DROP COLUMN IF EXISTS origem;
--   ALTER TABLE fazenda.animal  DROP COLUMN IF EXISTS reprodutor_espelho_id;
--   ALTER TABLE fazenda.animal  DROP COLUMN IF EXISTS uuid;
--   ALTER TABLE fazenda.animal  DROP COLUMN IF EXISTS grupo_id;
--   ALTER TABLE fazenda.animal  DROP COLUMN IF EXISTS eid;
--   DROP TABLE IF EXISTS fazenda.grupo_manejo;             -- por último (referenciada acima)
-- COMMIT;
-- =====================================================================
