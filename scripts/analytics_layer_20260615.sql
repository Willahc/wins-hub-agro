-- =============================================================================
-- Camada analytics — 2026-06-15
-- Schema novo e isolado: VIEWS (sempre frescas, custo zero de manutenção, drop trivial).
-- Consolida análises que hoje só existiam em queries ad-hoc, num lugar versionado.
-- Reverter tudo: DROP SCHEMA analytics CASCADE;
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS analytics;
GRANT USAGE ON SCHEMA analytics TO wins_app;

-- -----------------------------------------------------------------------------
-- 1) CATÁLOGO DE TOUROS — resumo por raça (DEP, central, genotipagem, oferta)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.vw_catalogo_resumo AS
SELECT COALESCE(ra.nome,'(sem raça)')                         AS raca,
       count(*)                                               AS reprodutores,
       count(*) FILTER (WHERE r.sexo='M')                     AS machos,
       count(*) FILTER (WHERE r.genotipado)                   AS genotipados,
       count(*) FILTER (WHERE r.em_central)                   AS em_central,
       count(*) FILTER (WHERE dep.reprodutor_id IS NOT NULL)  AS com_dep,
       count(*) FILTER (WHERE of.reprodutor_id IS NOT NULL)   AS com_oferta_comercial
FROM mercado.reprodutor r
LEFT JOIN catalogo.raca ra ON ra.id = r.raca_id
LEFT JOIN (SELECT DISTINCT reprodutor_id FROM mercado.avaliacao)  dep ON dep.reprodutor_id = r.id
LEFT JOIN (SELECT DISTINCT reprodutor_id FROM mercado.touro_oferta) of ON of.reprodutor_id = r.id
GROUP BY 1
ORDER BY 2 DESC;

-- -----------------------------------------------------------------------------
-- 2) CONTACTABILIDADE DO DECISOR por UF (WhatsApp/e-mail por CNPJ)
--    Junções por cnpj_basico varchar(8) — todas indexadas (rápido).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.vw_contactabilidade_uf AS
SELECT ld.uf,
       count(*)                                                   AS decisores,
       count(*) FILTER (WHERE w.cnpj_basico IS NOT NULL
                          OR fc.cnpj_basico IS NOT NULL)          AS com_whatsapp,
       count(*) FILTER (WHERE he.cnpj_basico IS NOT NULL
                          OR ev.cnpj_basico IS NOT NULL)          AS com_email,
       round(100.0*count(*) FILTER (WHERE w.cnpj_basico IS NOT NULL
                          OR fc.cnpj_basico IS NOT NULL)/count(*),1) AS pct_whatsapp
FROM prospeccao.lead_decisor ld
LEFT JOIN prospeccao.whatsapp_rfb w ON w.cnpj_basico = ld.cnpj_basico
LEFT JOIN prospeccao.fazenda_cel  fc ON fc.cnpj_basico = ld.cnpj_basico
LEFT JOIN prospeccao.hunter_email he ON he.cnpj_basico = ld.cnpj_basico
LEFT JOIN (SELECT DISTINCT cnpj_basico FROM prospeccao.email_valido) ev ON ev.cnpj_basico = ld.cnpj_basico
GROUP BY ld.uf
ORDER BY 2 DESC;

-- -----------------------------------------------------------------------------
-- 3) MONITOR DE QUALIDADE DE DADOS — uma linha por checagem, com severidade.
--    Roda sob demanda; serve de dashboard de saúde + alerta de viés/lacuna.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.vw_data_health AS
-- Viés geográfico: SP concentra a maioria dos decisores = artefato de enriquecimento
SELECT 'lead_decisor: concentração SP' AS checagem,
       round(100.0*count(*) FILTER (WHERE uf='SP')/count(*),1)::text||'%' AS valor,
       CASE WHEN 100.0*count(*) FILTER (WHERE uf='SP')/count(*) > 50
            THEN 'ALERTA: viés — não usar lead_decisor p/ distribuição por UF; usar prospect_genetica/matriz'
            ELSE 'ok' END AS nota
FROM prospeccao.lead_decisor
UNION ALL
-- Cobertura de decisor nomeado
SELECT 'lead_decisor: sem decisor_top',
       count(*) FILTER (WHERE decisor_top IS NULL OR decisor_top='')::text,
       'informativo' FROM prospeccao.lead_decisor
UNION ALL
-- Reprodutores sem raça (qualidade do catálogo)
SELECT 'reprodutor: sem raça',
       count(*) FILTER (WHERE raca_id IS NULL)::text,
       CASE WHEN count(*) FILTER (WHERE raca_id IS NULL)>0 THEN 'revisar mapeamento de raça' ELSE 'ok' END
FROM mercado.reprodutor
UNION ALL
-- Ofertas sem preço (acionabilidade comercial)
SELECT 'touro_oferta: sem preço',
       count(*) FILTER (WHERE preco_dose_brl IS NULL)::text,
       'informativo' FROM mercado.touro_oferta
UNION ALL
-- WhatsApp órfão (sem CNPJ no universo de decisores) = dado não aproveitado
SELECT 'whatsapp_rfb: órfão do lead_decisor',
       count(*)::text,
       CASE WHEN count(*)>0 THEN 'há WhatsApp sem match em lead_decisor — verificar cobertura do universo' ELSE 'ok' END
FROM prospeccao.whatsapp_rfb w
WHERE NOT EXISTS (SELECT 1 FROM prospeccao.lead_decisor ld WHERE ld.cnpj_basico=w.cnpj_basico)
UNION ALL
-- Frescor da matview principal (proxy de staleness do pipeline)
SELECT 'fazenda_nacional: linhas materializadas',
       count(*)::text, 'informativo' FROM prospeccao.fazenda_nacional;

COMMENT ON SCHEMA analytics IS 'Views analíticas consolidadas (catálogo, contactabilidade, saúde de dados) — criado 2026-06-15';
