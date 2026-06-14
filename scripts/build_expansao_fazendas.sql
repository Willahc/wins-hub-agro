-- Expansão da base de fazendas (jun/14): +18.373 fazendas de gado ATIVAS com CELULAR
-- que estavam fora da view (sem decisor nomeado). Itens: (1) ampliar base, (2) KPI
-- WhatsApp/Celular usa AMBOS os campos de telefone, (3) decisor via socio_rural.
-- Idempotente (INSERT guarda contra duplicata). Após rodar: já dá REFRESH na matview.

-- (2) celular WhatsApp-able de tel1 OU tel2, por cnpj_basico
DROP TABLE IF EXISTS prospeccao.fazenda_cel;
CREATE TABLE prospeccao.fazenda_cel AS
SELECT cnpj_basico, max(cel) AS whatsapp_cel
FROM (SELECT cnpj_basico,
        coalesce(prospeccao.cel_whats(NULLIF(ddd_1,'')||NULLIF(telefone_1,'')),
                 prospeccao.cel_whats(NULLIF(ddd_2,'')||NULLIF(telefone_2,''))) AS cel
      FROM cnpj.estabelecimento_rural) x
WHERE cel IS NOT NULL GROUP BY cnpj_basico;
CREATE INDEX ON prospeccao.fazenda_cel(cnpj_basico);

-- (1)+(3) as novas fazendas (bovinos ativas c/ celular, fora da view) + decisor
DROP TABLE IF EXISTS prospeccao.fazenda_expansao;
CREATE TABLE prospeccao.fazenda_expansao AS
WITH alvo AS (
  SELECT e.cnpj_basico FROM cnpj.estabelecimento_rural e
  WHERE e.cnpj_basico IN (SELECT cnpj_basico FROM prospeccao.fazenda_cel)
  GROUP BY e.cnpj_basico
  HAVING bool_or(e.situacao_cadastral='02') AND bool_or(left(lpad(e.cnae_fiscal_principal::text,7,'0'),5)='01512')
), novo AS (SELECT cnpj_basico FROM alvo WHERE cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.fazenda_nacional)),
estab AS (SELECT DISTINCT ON (cnpj_basico) cnpj_basico,cnpj_ordem,cnpj_dv,uf,municipio_nome,nome_fantasia
  FROM cnpj.estabelecimento_rural ORDER BY cnpj_basico,(identificador_matriz_filial='1') DESC,cnpj_ordem),
soc AS (SELECT cnpj_basico,
   string_agg(initcap(nome_socio)||coalesce(' ('||qualificacao_do_socio||')',''),'; ' ORDER BY identificador_de_socio) decisores,
   (array_agg(initcap(nome_socio) ORDER BY identificador_de_socio))[1] decisor_top
  FROM cnpj.socio_rural GROUP BY cnpj_basico)
SELECT n.cnpj_basico, e.cnpj_basico||e.cnpj_ordem||e.cnpj_dv cnpj14,
  initcap(coalesce(em.razao_social,e.nome_fantasia,'(produtor rural)')) razao,
  e.uf, initcap(e.municipio_nome) municipio, 'EXPANSAO_CELULAR'::text tipo,
  s.decisores, s.decisor_top, 'ATIVA'::text situacao_viva, em.porte::text porte, fc.whatsapp_cel
FROM novo n JOIN estab e ON e.cnpj_basico=n.cnpj_basico
JOIN prospeccao.fazenda_cel fc ON fc.cnpj_basico=n.cnpj_basico
LEFT JOIN cnpj.empresa_rural em ON em.cnpj_basico=n.cnpj_basico
LEFT JOIN soc s ON s.cnpj_basico=n.cnpj_basico;
GRANT SELECT ON prospeccao.fazenda_cel, prospeccao.fazenda_expansao TO wins_app;

-- (1) injeta na base; REFRESH carrega na matview que a página lê
INSERT INTO prospeccao.lead_decisor (cnpj_basico,cnpj14,razao,uf,municipio,tipo,decisores,decisor_top,situacao_viva,porte,qsa,linkedin,enriched_at)
SELECT cnpj_basico,cnpj14,razao,uf,municipio,tipo,decisores,decisor_top,situacao_viva,porte,NULL::jsonb,NULL,now()
FROM prospeccao.fazenda_expansao WHERE cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.lead_decisor);

-- (3) decisor dos EI/Produtor (natureza 4120/2135): a razão social É o nome da pessoa.
-- Limpa 'Em Recuperacao Judicial', 'E Outro(s)/Outra(s)' e CPF/números no fim.
UPDATE prospeccao.lead_decisor ld
SET decisor_top = d.dec, decisores = d.dec
FROM (
  SELECT l.cnpj_basico,
    btrim(regexp_replace(regexp_replace(regexp_replace(regexp_replace(l.razao,
      '\s+em recupera.*$','','i'), '\s+e outr[oa]s?$','','i'),
      '\s*[-0-9./]+\s*$',''), '^[0-9./\- ]+','')) AS dec   -- tira número no fim E no início
  FROM prospeccao.lead_decisor l
  JOIN cnpj.empresa_rural em ON em.cnpj_basico=l.cnpj_basico
  WHERE l.tipo='EXPANSAO_CELULAR' AND l.decisor_top IS NULL AND em.natureza_juridica IN ('4120','2135')
) d
WHERE ld.cnpj_basico=d.cnpj_basico AND ld.tipo='EXPANSAO_CELULAR' AND ld.decisor_top IS NULL AND length(d.dec)>=5;

REFRESH MATERIALIZED VIEW prospeccao.fazenda_nacional;
