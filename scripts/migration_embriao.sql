-- =====================================================================
-- Domínio EMBRIÃO / FIV — modelo de dados
-- Cria mercado.doadora (vaca doadora) e mercado.oferta_embriao (oferta de
-- embrião FIV/TE precificada). Estilo consistente com mercado.touro_oferta.
-- Brasil é o maior mercado bovino de FIV do mundo (Nelore de elite).
-- Idempotente (IF NOT EXISTS). GRANT para wins_app.
-- =====================================================================

SET search_path = mercado, catalogo, public;

-- ---------------------------------------------------------------------
-- DOADORA — vaca doadora de oócitos. Pode (ou não) já existir como fêmea
-- em mercado.reprodutor (sexo='F'); reprodutor_id liga quando casamos por
-- registro/nome.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mercado.doadora (
    id                serial PRIMARY KEY,
    reprodutor_id     integer REFERENCES mercado.reprodutor(id) ON DELETE SET NULL,
    nome              varchar(200) NOT NULL,
    nome_norm         varchar(200),               -- nome normalizado p/ match/dedup
    registro          varchar(50),
    raca_id           integer REFERENCES catalogo.raca(id),
    fazenda_origem    varchar(200),
    uf                char(2),
    fonte_referencia  varchar(100),
    fonte_url         varchar(500),
    coletado_em       timestamp DEFAULT now()
);

-- dedup: mesma doadora (nome normalizado) dentro da mesma raça
CREATE UNIQUE INDEX IF NOT EXISTS uniq_doadora_nome_raca
    ON mercado.doadora (nome_norm, raca_id)
    WHERE nome_norm IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_doadora_reprodutor ON mercado.doadora (reprodutor_id);
CREATE INDEX IF NOT EXISTS idx_doadora_raca       ON mercado.doadora (raca_id);

-- ---------------------------------------------------------------------
-- OFERTA_EMBRIAO — oferta precificada de embrião (acasalamento doadora x touro)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mercado.oferta_embriao (
    id                serial PRIMARY KEY,
    doadora_id        integer REFERENCES mercado.doadora(id) ON DELETE SET NULL,
    doadora_nome      varchar(200),               -- nome cru (mesmo sem match)
    reprodutor_id     integer REFERENCES mercado.reprodutor(id) ON DELETE SET NULL, -- touro/sire
    touro_nome        varchar(200),               -- nome cru do touro/sire
    raca_id           integer REFERENCES catalogo.raca(id),
    tipo              varchar(8) NOT NULL DEFAULT 'FIV'    -- 'FIV' | 'TE'
                      CHECK (tipo IN ('FIV', 'TE')),
    categoria         varchar(40),                -- ex: STANDARD / PREMIUM / PO / DT
    qtd               integer,                    -- nº de embriões no lote (NULL = unitário)
    preco_brl         numeric(12,2),              -- preço por embrião (ou do lote, ver preco_por)
    preco_por         varchar(10) DEFAULT 'embriao'   -- 'embriao' | 'lote'
                      CHECK (preco_por IN ('embriao', 'lote')),
    fonte_referencia  varchar(100),               -- ex: 'crv_loja'
    leilao_nome       varchar(200),               -- quando vier de leilão
    data_evento       date,                       -- data do leilão/oferta
    fonte_url         varchar(500),
    external_id       varchar(60),                -- id/SKU na fonte (dedup)
    coletado_em       timestamp DEFAULT now()
);

-- dedup por SKU/external da fonte
CREATE UNIQUE INDEX IF NOT EXISTS uniq_oferta_embriao_external
    ON mercado.oferta_embriao (fonte_referencia, external_id)
    WHERE external_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_oferta_embriao_doadora   ON mercado.oferta_embriao (doadora_id);
CREATE INDEX IF NOT EXISTS idx_oferta_embriao_reprodutor ON mercado.oferta_embriao (reprodutor_id);
CREATE INDEX IF NOT EXISTS idx_oferta_embriao_raca      ON mercado.oferta_embriao (raca_id);
CREATE INDEX IF NOT EXISTS idx_oferta_embriao_preco     ON mercado.oferta_embriao (preco_brl)
    WHERE preco_brl IS NOT NULL;

-- ---------------------------------------------------------------------
-- GRANTS — app só lê
-- ---------------------------------------------------------------------
GRANT SELECT ON mercado.doadora        TO wins_app;
GRANT SELECT ON mercado.oferta_embriao TO wins_app;
GRANT USAGE  ON SEQUENCE mercado.doadora_id_seq        TO wins_app;
GRANT USAGE  ON SEQUENCE mercado.oferta_embriao_id_seq TO wins_app;
