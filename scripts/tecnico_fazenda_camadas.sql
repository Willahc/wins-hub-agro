-- ============================================================================
-- Camadas técnico↔fazenda (jun/2026) — DDL idempotente reproduzível.
-- Posse(C1) + Programa(C2) + Proximidade(C3) + base CAR nacional(C4) + UI/NDVI.
-- Pré-req: prospeccao.imovel_rural carregada (scripts/load_car_nacional.py),
--          mv_herd_mun, v_tecnico_full, tecnico_nelore, rebanho_elite, referencia.municipio.
-- Recriar tudo: psql -f scripts/tecnico_fazenda_camadas.sql ; depois REFRESH se a base mudar.
-- ============================================================================

-- C4: constraints da imovel_rural permitem múltiplos NULL (CAR não tem codigo_sigef)
ALTER TABLE prospeccao.imovel_rural DROP CONSTRAINT IF EXISTS imovel_rural_codigo_sigef_key;
ALTER TABLE prospeccao.imovel_rural ADD  CONSTRAINT imovel_rural_codigo_sigef_key UNIQUE NULLS DISTINCT (codigo_sigef);
ALTER TABLE prospeccao.imovel_rural DROP CONSTRAINT IF EXISTS imovel_rural_codigo_car_key;
ALTER TABLE prospeccao.imovel_rural ADD  CONSTRAINT imovel_rural_codigo_car_key UNIQUE NULLS DISTINCT (codigo_car);
CREATE INDEX IF NOT EXISTS idx_imovel_latlon ON prospeccao.imovel_rural(latitude, longitude) WHERE fonte_principal='SICAR';
CREATE INDEX IF NOT EXISTS idx_imovel_mun_car ON prospeccao.imovel_rural(codigo_ibge_mun) WHERE fonte_principal='SICAR';

-- ---- mv_tecnico_geo ----
DROP MATERIALIZED VIEW IF EXISTS prospeccao.mv_tecnico_geo CASCADE;
CREATE MATERIALIZED VIEW prospeccao.mv_tecnico_geo AS
 SELECT f.cnpj14,
    f.nome,
    f.tier,
    m.codigo_ibge,
    m.nome_normalizado AS mun,
    m.uf,
    m.latitude AS lat,
    m.longitude AS lon
   FROM prospeccao.v_tecnico_full f
     JOIN cnpj.estabelecimento_vet e ON e.cnpj_basico::text = substr(f.cnpj14, 1, 8) AND e.cnpj_ordem::text = substr(f.cnpj14, 9, 4) AND e.cnpj_dv::text = substr(f.cnpj14, 13, 2)
     JOIN referencia.municipio m ON m.codigo_tom = e.municipio::integer AND m.uf::text = e.uf::text
  WHERE f.categoria IS NOT NULL AND (f.tier = ANY (ARRAY['A-inseminador'::text, 'B-corte-alto'::text, 'C-corte-medio'::text, 'D-corte-baixo'::text])) AND f.nome !~ '^[0-9]'::text AND m.latitude IS NOT NULL;

-- ---- mv_tecnico_fazenda_posse ----
DROP MATERIALIZED VIEW IF EXISTS prospeccao.mv_tecnico_fazenda_posse CASCADE;
CREATE MATERIALIZED VIEW prospeccao.mv_tecnico_fazenda_posse AS
 WITH tq AS (
         SELECT v_tecnico_full.cnpj14,
            substr(v_tecnico_full.cnpj14, 1, 8) AS vb,
            upper(btrim(v_tecnico_full.nome)) AS nome_k,
            v_tecnico_full.nome AS tecnico_nome,
            v_tecnico_full.profissao,
            v_tecnico_full.tier,
            v_tecnico_full.uf AS tec_uf,
            v_tecnico_full.tel_melhor,
            v_tecnico_full.whatsapp,
            v_tecnico_full.celular,
            v_tecnico_full.instagram,
            v_tecnico_full.crmv,
            v_tecnico_full.crmv_confiavel
           FROM prospeccao.v_tecnico_full
          WHERE v_tecnico_full.categoria IS NOT NULL AND (v_tecnico_full.tier = ANY (ARRAY['A-inseminador'::text, 'B-corte-alto'::text, 'C-corte-medio'::text, 'D-corte-baixo'::text])) AND v_tecnico_full.nome !~ '^[0-9]'::text
        ), sv AS (
         SELECT DISTINCT s.cnpj_basico AS vb,
            s.cnpj_cpf_do_socio AS cpf,
            upper(btrim(s.nome_socio)) AS nome_k
           FROM cnpj.socio_vet s
          WHERE s.identificador_de_socio::text = '2'::text AND s.cnpj_cpf_do_socio ~ '[0-9]'::text
        ), sr AS (
         SELECT DISTINCT s.cnpj_cpf_do_socio AS cpf,
            upper(btrim(s.nome_socio)) AS nome_k,
            s.cnpj_basico AS rb
           FROM cnpj.socio_rural s
          WHERE s.identificador_de_socio::text = '2'::text AND s.cnpj_cpf_do_socio ~ '[0-9]'::text
        ), faz AS (
         SELECT DISTINCT ON (estabelecimento_rural.cnpj_basico) estabelecimento_rural.cnpj_basico AS rb,
            (estabelecimento_rural.cnpj_basico::text || estabelecimento_rural.cnpj_ordem::text) || estabelecimento_rural.cnpj_dv::text AS faz_cnpj14,
            estabelecimento_rural.cnae_fiscal_principal AS cnae,
            estabelecimento_rural.nome_fantasia AS faz_nome,
            estabelecimento_rural.municipio_nome AS faz_mun,
            estabelecimento_rural.uf AS faz_uf,
            estabelecimento_rural.municipio AS faz_mun_cod,
            (initcap(COALESCE(estabelecimento_rural.tipo_logradouro || ' '::text, ''::text) || estabelecimento_rural.logradouro) || ', '::text) || estabelecimento_rural.numero AS faz_endereco,
            estabelecimento_rural.cep AS faz_cep
           FROM cnpj.estabelecimento_rural
          WHERE estabelecimento_rural.situacao_cadastral::text = '02'::text AND estabelecimento_rural.cnae_fiscal_principal::text ~~ '0151%'::text
          ORDER BY estabelecimento_rural.cnpj_basico, estabelecimento_rural.identificador_matriz_filial
        )
 SELECT tq.cnpj14 AS tecnico_cnpj14,
    tq.tecnico_nome,
    tq.profissao,
    tq.tier,
    tq.tec_uf,
    tq.tel_melhor,
    tq.whatsapp,
    tq.celular,
    tq.instagram,
    tq.crmv,
    tq.crmv_confiavel,
    faz.faz_cnpj14,
    faz.faz_nome,
        CASE faz.cnae
            WHEN '0151201'::text THEN 'corte'::text
            WHEN '0151202'::text THEN 'leite'::text
            ELSE 'outro'::text
        END AS faz_tipo,
    faz.faz_endereco,
    faz.faz_mun,
    faz.faz_uf,
    faz.faz_cep,
    m.latitude AS faz_lat,
    m.longitude AS faz_lon,
    tq.tec_uf::text <> faz.faz_uf::text AS fazenda_outra_uf
   FROM tq
     JOIN sv ON sv.vb::text = tq.vb AND sv.nome_k = tq.nome_k
     JOIN sr ON sr.cpf = sv.cpf AND sr.nome_k = sv.nome_k
     JOIN faz ON faz.rb::text = sr.rb::text
     LEFT JOIN referencia.municipio m ON m.codigo_tom = faz.faz_mun_cod::integer;
CREATE INDEX idx_tfp_tec ON prospeccao.mv_tecnico_fazenda_posse USING btree (tecnico_cnpj14);
CREATE INDEX idx_tfp_uf ON prospeccao.mv_tecnico_fazenda_posse USING btree (faz_uf);

-- ---- mv_herd_geo ----
DROP MATERIALIZED VIEW IF EXISTS prospeccao.mv_herd_geo CASCADE;
CREATE MATERIALIZED VIEW prospeccao.mv_herd_geo AS
 SELECT m.codigo_ibge,
    m.nome_normalizado AS nome_norm,
    m.uf,
    m.latitude AS lat,
    m.longitude AS lon,
    h.bovinos,
    COALESCE(f.fazendas_corte, 0::bigint) AS fazendas_corte
   FROM referencia.municipio m
     JOIN prospeccao.mv_herd_mun h ON h.nome_norm = m.nome_normalizado::text AND h.uf = m.uf::text
     LEFT JOIN ( SELECT estabelecimento_rural.municipio AS mun_cod,
            estabelecimento_rural.uf,
            count(*) AS fazendas_corte
           FROM cnpj.estabelecimento_rural
          WHERE estabelecimento_rural.situacao_cadastral::text = '02'::text AND estabelecimento_rural.cnae_fiscal_principal::text = '0151201'::text
          GROUP BY estabelecimento_rural.municipio, estabelecimento_rural.uf) f ON f.mun_cod::text = m.codigo_tom::text AND f.uf::text = m.uf::text
  WHERE m.latitude IS NOT NULL;
CREATE INDEX idx_herdgeo_ll ON prospeccao.mv_herd_geo USING btree (lat, lon);

-- ---- mv_mun_proximidade ----
DROP MATERIALIZED VIEW IF EXISTS prospeccao.mv_mun_proximidade CASCADE;
CREATE MATERIALIZED VIEW prospeccao.mv_mun_proximidade AS
 WITH tm AS (
         SELECT DISTINCT mv_tecnico_geo.codigo_ibge,
            mv_tecnico_geo.mun,
            mv_tecnico_geo.uf,
            mv_tecnico_geo.lat,
            mv_tecnico_geo.lon
           FROM prospeccao.mv_tecnico_geo
        )
 SELECT tm.codigo_ibge,
    tm.mun,
    tm.uf,
    tm.lat,
    tm.lon,
    sum(d.bovinos) FILTER (WHERE d.km <= 100::double precision) AS bovinos_100km,
    sum(d.fazendas_corte) FILTER (WHERE d.km <= 100::double precision) AS fazendas_100km,
    count(*) FILTER (WHERE d.km <= 100::double precision) AS municipios_100km,
    sum(d.bovinos) FILTER (WHERE d.km <= 50::double precision) AS bovinos_50km,
    sum(d.fazendas_corte) FILTER (WHERE d.km <= 50::double precision) AS fazendas_50km
   FROM tm
     JOIN LATERAL ( SELECT hg.bovinos,
            hg.fazendas_corte,
            6371::double precision * acos(LEAST(1::double precision, GREATEST('-1'::integer::double precision, sin(radians(tm.lat::double precision)) * sin(radians(hg.lat::double precision)) + cos(radians(tm.lat::double precision)) * cos(radians(hg.lat::double precision)) * cos(radians((hg.lon - tm.lon)::double precision))))) AS km
           FROM prospeccao.mv_herd_geo hg
          WHERE hg.lat >= (tm.lat - 1.0) AND hg.lat <= (tm.lat + 1.0) AND hg.lon >= (tm.lon - 1.2) AND hg.lon <= (tm.lon + 1.2)) d ON true
  GROUP BY tm.codigo_ibge, tm.mun, tm.uf, tm.lat, tm.lon;
CREATE INDEX idx_munprox_ibge ON prospeccao.mv_mun_proximidade USING btree (codigo_ibge);

-- ---- mv_tecnico_proximidade ----
DROP MATERIALIZED VIEW IF EXISTS prospeccao.mv_tecnico_proximidade CASCADE;
CREATE MATERIALIZED VIEW prospeccao.mv_tecnico_proximidade AS
 SELECT g.cnpj14,
    g.nome,
    g.tier,
    g.mun,
    g.uf,
    p.bovinos_100km,
    p.fazendas_100km,
    p.municipios_100km,
    p.bovinos_50km,
    p.fazendas_50km,
    round(100.0::double precision * percent_rank() OVER (ORDER BY p.bovinos_100km NULLS FIRST))::integer AS score_canal
   FROM prospeccao.mv_tecnico_geo g
     JOIN prospeccao.mv_mun_proximidade p ON p.codigo_ibge = g.codigo_ibge;
CREATE INDEX idx_tecprox_cnpj ON prospeccao.mv_tecnico_proximidade USING btree (cnpj14);

-- ---- mv_mun_prox_real ----
DROP MATERIALIZED VIEW IF EXISTS prospeccao.mv_mun_prox_real CASCADE;
CREATE MATERIALIZED VIEW prospeccao.mv_mun_prox_real AS
 WITH tm AS (
         SELECT DISTINCT mv_tecnico_geo.codigo_ibge,
            mv_tecnico_geo.mun,
            mv_tecnico_geo.uf,
            mv_tecnico_geo.lat,
            mv_tecnico_geo.lon
           FROM prospeccao.mv_tecnico_geo
        )
 SELECT tm.codigo_ibge,
    tm.mun,
    tm.uf,
    count(*) FILTER (WHERE d.km <= 30::double precision) AS fazendas_real_30km,
    count(*) FILTER (WHERE d.km <= 50::double precision) AS fazendas_real_50km,
    round(sum(d.area) FILTER (WHERE d.km <= 30::double precision)) AS ha_real_30km,
    round(sum(d.area) FILTER (WHERE d.km <= 50::double precision)) AS ha_real_50km
   FROM tm
     JOIN LATERAL ( SELECT i.area_total_ha AS area,
            6371::double precision * acos(LEAST(1::double precision, GREATEST('-1'::integer::double precision, sin(radians(tm.lat::double precision)) * sin(radians(i.latitude::double precision)) + cos(radians(tm.lat::double precision)) * cos(radians(i.latitude::double precision)) * cos(radians((i.longitude - tm.lon)::double precision))))) AS km
           FROM prospeccao.imovel_rural i
          WHERE i.fonte_principal::text = 'SICAR'::text AND i.area_total_ha >= 100::numeric AND i.latitude >= (tm.lat - 0.5) AND i.latitude <= (tm.lat + 0.5) AND i.longitude >= (tm.lon - 0.55) AND i.longitude <= (tm.lon + 0.55)) d ON true
  GROUP BY tm.codigo_ibge, tm.mun, tm.uf;
CREATE INDEX idx_munproxreal ON prospeccao.mv_mun_prox_real USING btree (codigo_ibge);

-- ---- v_consultor_rebanho_elite ----
DROP VIEW IF EXISTS prospeccao.v_consultor_rebanho_elite CASCADE;
CREATE VIEW prospeccao.v_consultor_rebanho_elite AS
 SELECT t.nome AS consultor,
    t.programa,
    t.papel,
    t.regiao,
    t.uf,
    t.contato,
    t.tipo_contato,
    r.fazenda,
    r.proprietario,
    r.municipio AS faz_municipio,
    r.uf AS faz_uf,
    r.telefone AS faz_telefone,
    r.instagram AS faz_instagram,
    r.animais_ceip
   FROM prospeccao.tecnico_nelore t
     JOIN prospeccao.rebanho_elite r ON r.uf = t.uf AND t.uf <> ''::text;

-- ---- v_tecnico_fazenda ----
DROP VIEW IF EXISTS prospeccao.v_tecnico_fazenda CASCADE;
CREATE VIEW prospeccao.v_tecnico_fazenda AS
 SELECT f.cnpj14,
    f.nome AS tecnico,
    f.profissao,
    f.tier,
    f.uf,
    f.tel_melhor,
    f.whatsapp,
    f.celular,
    f.instagram,
    f.crmv,
    f.crmv_confiavel,
    f.sinal_corte,
    px.bovinos_100km,
    px.fazendas_100km,
    px.score_canal,
    po.n_fazendas_posse,
    po.fazendas_posse,
    po.n_fazendas_posse IS NOT NULL AS tem_fazenda_propria,
    cn.nome IS NOT NULL AS consultor_programa_elite
   FROM prospeccao.v_tecnico_full f
     LEFT JOIN prospeccao.mv_tecnico_proximidade px ON px.cnpj14 = f.cnpj14
     LEFT JOIN ( SELECT mv_tecnico_fazenda_posse.tecnico_cnpj14,
            count(DISTINCT mv_tecnico_fazenda_posse.faz_cnpj14) AS n_fazendas_posse,
            string_agg(DISTINCT ((((COALESCE(mv_tecnico_fazenda_posse.faz_nome, ''::text) || ' ('::text) || mv_tecnico_fazenda_posse.faz_mun) || '/'::text) || mv_tecnico_fazenda_posse.faz_uf::text) || ')'::text, ' | '::text) AS fazendas_posse
           FROM prospeccao.mv_tecnico_fazenda_posse
          GROUP BY mv_tecnico_fazenda_posse.tecnico_cnpj14) po ON po.tecnico_cnpj14 = f.cnpj14
     LEFT JOIN prospeccao.tecnico_nelore cn ON upper(btrim(cn.nome)) = upper(btrim(f.nome))
  WHERE f.categoria IS NOT NULL AND (f.tier = ANY (ARRAY['A-inseminador'::text, 'B-corte-alto'::text, 'C-corte-medio'::text, 'D-corte-baixo'::text])) AND f.nome !~ '^[0-9]'::text;

-- ---- v_tecnico_fazenda_ui ----
DROP VIEW IF EXISTS prospeccao.v_tecnico_fazenda_ui CASCADE;
CREATE VIEW prospeccao.v_tecnico_fazenda_ui AS
 SELECT t.cnpj14,
    t.cnpj_basico,
    t.nome,
    t.fonte_nome,
    t.categoria,
    t.tier,
    t.municipio,
    t.uf,
    t.tel_receita,
    t.email_receita,
    t.whatsapp,
    t.celular,
    t.instagram,
    t.site,
    t.tel_melhor,
    t.crmv,
    t.crmv_uf,
    t.crmv_cat,
    t.crmv_confiavel,
    t.profissao,
    t.sinal_corte,
    t.bovinos_municipio,
    t.vets_por_100k_cab,
    t.enriquecido_serper,
    px.bovinos_100km,
    px.fazendas_100km,
    px.score_canal,
    pr.fazendas_real_50km,
    pr.ha_real_50km,
    pr.fazendas_real_30km,
    po.n_fazendas_posse,
    po.fazendas_posse,
    po.tecnico_cnpj14 IS NOT NULL AS tem_fazenda_propria
   FROM prospeccao.v_tecnico_full t
     LEFT JOIN prospeccao.mv_tecnico_proximidade px ON px.cnpj14 = t.cnpj14
     LEFT JOIN prospeccao.mv_tecnico_geo g ON g.cnpj14 = t.cnpj14
     LEFT JOIN prospeccao.mv_mun_prox_real pr ON pr.codigo_ibge = g.codigo_ibge
     LEFT JOIN ( SELECT mv_tecnico_fazenda_posse.tecnico_cnpj14,
            count(DISTINCT mv_tecnico_fazenda_posse.faz_cnpj14) AS n_fazendas_posse,
            string_agg(DISTINCT (((COALESCE(NULLIF(mv_tecnico_fazenda_posse.faz_nome, ''::text), '(s/ nome)'::text) || ' — '::text) || mv_tecnico_fazenda_posse.faz_mun) || '/'::text) || mv_tecnico_fazenda_posse.faz_uf::text, ' · '::text) AS fazendas_posse
           FROM prospeccao.mv_tecnico_fazenda_posse
          GROUP BY mv_tecnico_fazenda_posse.tecnico_cnpj14) po ON po.tecnico_cnpj14 = t.cnpj14;

