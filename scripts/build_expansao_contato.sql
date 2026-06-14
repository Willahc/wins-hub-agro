-- Expansao 2 (jun/14): +35.818 fazendas de gado ATIVAS com e-mail OU telefone fixo (sem celular),
-- fora da view. Decisor: socio_rural + razao social p/ EI/produtor. Idempotente. Base 164.671 -> 200.489.
INSERT INTO prospeccao.lead_decisor (cnpj_basico,cnpj14,razao,uf,municipio,tipo,decisores,decisor_top,situacao_viva,porte,qsa,linkedin,enriched_at)
WITH er AS (
  SELECT cnpj_basico, bool_or(situacao_cadastral='02') ativa,
    bool_or(left(lpad(cnae_fiscal_principal::text,7,'0'),5)='01512') bovinos,
    bool_or(correio_eletronico ~* '@') email,
    bool_or(NULLIF(telefone_1,'') IS NOT NULL OR NULLIF(telefone_2,'') IS NOT NULL) tel
  FROM cnpj.estabelecimento_rural GROUP BY cnpj_basico),
novo AS (SELECT cnpj_basico FROM er WHERE ativa AND bovinos AND (email OR tel)
  AND cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.lead_decisor)),
estab AS (SELECT DISTINCT ON (cnpj_basico) cnpj_basico,cnpj_ordem,cnpj_dv,uf,municipio_nome,nome_fantasia
  FROM cnpj.estabelecimento_rural ORDER BY cnpj_basico,(identificador_matriz_filial='1') DESC,cnpj_ordem),
soc AS (SELECT cnpj_basico,
   string_agg(initcap(nome_socio)||coalesce(' ('||qualificacao_do_socio||')',''),'; ' ORDER BY identificador_de_socio) decisores,
   (array_agg(initcap(nome_socio) ORDER BY identificador_de_socio))[1] decisor_top
  FROM cnpj.socio_rural GROUP BY cnpj_basico)
SELECT n.cnpj_basico, e.cnpj_basico||e.cnpj_ordem||e.cnpj_dv,
  initcap(coalesce(em.razao_social,e.nome_fantasia,'(produtor rural)')),
  e.uf, initcap(e.municipio_nome), 'EXPANSAO_CONTATO', s.decisores, s.decisor_top,
  'ATIVA', em.porte::text, NULL::jsonb, NULL, now()
FROM novo n JOIN estab e ON e.cnpj_basico=n.cnpj_basico
LEFT JOIN cnpj.empresa_rural em ON em.cnpj_basico=n.cnpj_basico
LEFT JOIN soc s ON s.cnpj_basico=n.cnpj_basico;

UPDATE prospeccao.lead_decisor ld SET decisor_top=d.dec, decisores=d.dec
FROM (SELECT l.cnpj_basico,
   btrim(regexp_replace(regexp_replace(regexp_replace(regexp_replace(l.razao,
     '\s+em recupera.*$','','i'),'\s+e outr[oa]s?$','','i'),'\s*[-0-9./]+\s*$',''),'^[0-9./\- ]+','')) dec
  FROM prospeccao.lead_decisor l JOIN cnpj.empresa_rural em ON em.cnpj_basico=l.cnpj_basico
  WHERE l.tipo='EXPANSAO_CONTATO' AND l.decisor_top IS NULL AND em.natureza_juridica IN ('4120','2135')) d
WHERE ld.cnpj_basico=d.cnpj_basico AND ld.tipo='EXPANSAO_CONTATO' AND ld.decisor_top IS NULL AND length(d.dec)>=5;

REFRESH MATERIALIZED VIEW prospeccao.fazenda_nacional;

-- cleanup geral: tira prefixo numérico de qualquer decisor de expansão (sócio incluso)
UPDATE prospeccao.lead_decisor
SET decisor_top=btrim(regexp_replace(decisor_top,'^[0-9./\- ]+','')),
    decisores=btrim(regexp_replace(decisores,'^[0-9./\- ]+',''))
WHERE tipo LIKE 'EXPANSAO%' AND decisor_top ~ '^[0-9]';
REFRESH MATERIALIZED VIEW prospeccao.fazenda_nacional;
