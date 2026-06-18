-- =============================================================================
-- Triagem dos vets órfãos: manter SÓ quem lida com PECUÁRIA — 2026-06-15, ZERO API.
-- Universo: 28.916 vets (CNAE 7500100) ativos, órfãos de WhatsApp.
-- Regra multi-sinal (todos internos):
--   VÁLIDO se NÃO tem nome explícito de pet E (
--       rebanho do município >= 20k cabeças            -- território de pecuária real
--    OR CNAE secundário de pecuária/comércio agro      -- atividade declarada
--    OR nome com termo de pecuária                      -- evidência no nome
--    OR (rebanho 5k–20k E município não é capital) )    -- interior pecuário médio
--   classe FORTE = 1º-3º sinais ; PROVAVEL = só o 4º.
-- Decisor = sócio PF de melhor cargo (cnpj.socio_rural). WhatsApp = whatsapp_rfb.
-- Reverter: DROP TABLE prospeccao.vet_pecuaria;
-- =============================================================================
DROP TABLE IF EXISTS prospeccao.vet_pecuaria;
CREATE TABLE prospeccao.vet_pecuaria AS
WITH qual(code,label,prio) AS (VALUES
  ('49','Sócio-Administrador',1),('65','Titular',2),('05','Administrador',2),
  ('16','Presidente',3),('59','Produtor Rural',3),('10','Diretor',4),
  ('22','Sócio',6),('30','Sócio/Acionista',7),('38','Sócio',7)),
base AS (
  SELECT DISTINCT ON (e.cnpj_basico)
    e.cnpj_basico,
    e.cnpj_basico||e.cnpj_ordem||e.cnpj_dv AS cnpj14,
    COALESCE(NULLIF(em.razao_social,''), e.nome_fantasia,'') AS razao,
    e.uf, e.municipio_nome AS municipio, e.municipio AS tom,
    e.cnae_fiscal_secundaria AS cnae2,
    w.whatsapp
  FROM prospeccao.whatsapp_rfb w
  JOIN cnpj.estabelecimento_rural e ON e.cnpj_basico=w.cnpj_basico
  LEFT JOIN cnpj.empresa_rural em ON em.cnpj_basico=e.cnpj_basico
  WHERE NOT EXISTS (SELECT 1 FROM prospeccao.lead_decisor ld WHERE ld.cnpj_basico=w.cnpj_basico)
    AND e.cnae_fiscal_principal='7500100' AND e.situacao_cadastral='02'
  ORDER BY e.cnpj_basico, (e.identificador_matriz_filial::text='1') DESC
),
sig AS (
  SELECT b.*,
    COALESCE(h.bovinos,0) AS herd,
    COALESCE(m.capital,false) AS capital,
    (b.razao ~* '\mpet\M|petshop|pet shop|aquari|estima|companhia|\mcao\M|\mcães\M|\mgato|silvestr|banho.*tosa') AS pet_kw,
    (b.razao ~* 'agropec|rural|pecu|bovin|\mgado\M|fazenda|\mcampo\M|leite|grande.?anim|\mboi\M|confina|nelore|angus') AS gado_kw,
    (b.cnae2 ~ '(^|,)(015[12]|0162|4623|4692)') AS cnae2_agro
  FROM base b
  LEFT JOIN referencia.municipio m ON m.codigo_tom = NULLIF(b.tom,'')::int
  LEFT JOIN prospeccao.mv_herd_geo h ON h.codigo_ibge=m.codigo_ibge
),
soc AS (
  SELECT s.cnpj_basico,
    (s.nome_socio||' ('||COALESCE(q.label,'Sócio')||')') AS decisor_top,
    row_number() OVER (PARTITION BY s.cnpj_basico ORDER BY COALESCE(q.prio,6), s.nome_socio) rn
  FROM cnpj.socio_rural s
  JOIN sig ON sig.cnpj_basico=s.cnpj_basico
  LEFT JOIN qual q ON q.code=s.qualificacao_do_socio
  WHERE s.identificador_de_socio<>'1' AND NULLIF(trim(s.nome_socio),'') IS NOT NULL
)
SELECT s.cnpj_basico, s.cnpj14, s.razao,
       COALESCE(t.decisor_top, s.razao||' (vet)') AS decisor_top,
       s.uf, s.municipio, s.whatsapp, s.herd AS herd_municipio, s.capital,
       CASE WHEN (s.herd>=20000 OR s.cnae2_agro OR s.gado_kw) THEN 'FORTE' ELSE 'PROVAVEL' END AS classe,
       array_to_string(ARRAY[
         CASE WHEN s.herd>=20000 THEN 'herd>=20k' WHEN s.herd>=5000 THEN 'herd5-20k' END,
         CASE WHEN s.cnae2_agro THEN 'cnae2-agro' END,
         CASE WHEN s.gado_kw THEN 'nome-gado' END], ',') AS sinais,
       now() AS criado_em
FROM sig s
LEFT JOIN soc t ON t.cnpj_basico=s.cnpj_basico AND t.rn=1
WHERE NOT s.pet_kw
  AND ( s.herd>=20000 OR s.cnae2_agro OR s.gado_kw OR (s.herd>=5000 AND NOT s.capital) );

ALTER TABLE prospeccao.vet_pecuaria ADD PRIMARY KEY (cnpj_basico);
CREATE INDEX idx_vet_pecuaria_uf ON prospeccao.vet_pecuaria(uf);
GRANT SELECT ON prospeccao.vet_pecuaria TO wins_app;
