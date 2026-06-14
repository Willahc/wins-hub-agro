-- PRODUTO "Carteira do Técnico" (jun/14): canal de venda indireto.
-- Liga cada técnico/empresa às fazendas que compartilham o MESMO telefone+UF (fone_key).
-- Granularidade = (telefone, UF) = o "hub" do canal — evita carteiras duplicadas quando
-- vários técnicos dividem o número de uma central/empresa. Lista TODOS os nomes do número.
-- celular = vet pessoal (link forte); fixo = clínica/central/empresa (atende cluster).
-- Cap 2..80 fazendas: <2 não é carteira; >80 = número genérico (contador) = ruído.
DROP MATERIALIZED VIEW IF EXISTS prospeccao.tecnico_carteira;
CREATE MATERIALIZED VIEW prospeccao.tecnico_carteira AS
WITH tk AS (
  SELECT t.cnpj_basico AS tec_cnpj, initcap(t.nome) AS nome, t.uf,
         COALESCE(NULLIF(t.profissao,''),'téc') AS prof, NULLIF(t.crmv,'') AS crmv,
         COALESCE(t.whatsapp,t.celular,t.tel_receita) AS contato, kk.k
  FROM prospeccao.tecnico_social t
  CROSS JOIN LATERAL (SELECT DISTINCT k FROM unnest(ARRAY[
        prospeccao.fone_key(t.whatsapp), prospeccao.fone_key(t.celular), prospeccao.fone_key(t.tel_receita)]) k
      WHERE k IS NOT NULL) kk
  WHERE t.uf IS NOT NULL AND t.nome !~ '^[0-9]'
),
fk AS (
  SELECT f.cnpj_basico, f.cnpj_completo, f.nome_fazenda, f.municipio, f.uf,
         f.sinal_genetico, f.touros_nelore, kk.k
  FROM prospeccao.fazenda_nacional f
  CROSS JOIN LATERAL (SELECT DISTINCT k FROM unnest(ARRAY[
        prospeccao.fone_key(f.telefone_rfb), prospeccao.fone_key(f.whatsapp), prospeccao.fone_key(f.celular)]) k
      WHERE k IS NOT NULL) kk
),
link AS (
  SELECT DISTINCT tk.k, tk.uf, fk.cnpj_basico, fk.cnpj_completo, fk.nome_fazenda,
         fk.municipio, fk.sinal_genetico, fk.touros_nelore
  FROM tk JOIN fk ON fk.k=tk.k AND fk.uf=tk.uf AND fk.cnpj_basico<>tk.tec_cnpj
),
tecs AS (
  SELECT k, uf,
    count(DISTINCT nome) AS n_tecnicos,
    (array_agg(nome      ORDER BY (crmv IS NOT NULL) DESC, nome))[1] AS tec_principal,
    (array_agg(tec_cnpj  ORDER BY (crmv IS NOT NULL) DESC, nome))[1] AS tec_cnpj,
    (array_agg(prof    ORDER BY (crmv IS NOT NULL) DESC, nome))[1] AS prof,
    (array_agg(crmv    ORDER BY (crmv IS NOT NULL) DESC))[1]       AS crmv,
    (array_agg(contato ORDER BY (contato IS NOT NULL) DESC))[1]    AS contato,
    string_agg(DISTINCT nome, ' · ' ORDER BY nome)                AS tecnicos_todos
  FROM tk GROUP BY k, uf
)
SELECT row_number() OVER (ORDER BY count(DISTINCT l.cnpj_basico) DESC, t.uf) AS id,
   t.k AS fone_key, t.uf, t.tec_principal, t.tec_cnpj, t.prof, t.crmv, t.contato,
   t.n_tecnicos, t.tecnicos_todos,
   CASE WHEN substr(t.k,3,1) IN ('6','7','8','9') THEN 'celular' ELSE 'fixo' END AS fone_tipo,
   count(DISTINCT l.cnpj_basico) AS n_fazendas,
   count(DISTINCT l.cnpj_basico) FILTER (WHERE l.sinal_genetico='alta')  AS n_alta,
   sum(COALESCE(l.touros_nelore,0))                                      AS touros_total,
   jsonb_agg(DISTINCT jsonb_build_object('cnpj', regexp_replace(l.cnpj_completo,'\D','','g'),
        'nome', initcap(l.nome_fazenda), 'municipio', l.municipio,
        'sinal', l.sinal_genetico, 'touros', l.touros_nelore)) AS fazendas
FROM tecs t JOIN link l ON l.k=t.k AND l.uf=t.uf
GROUP BY t.k, t.uf, t.tec_principal, t.tec_cnpj, t.prof, t.crmv, t.contato, t.n_tecnicos, t.tecnicos_todos
HAVING count(DISTINCT l.cnpj_basico) BETWEEN 2 AND 80;
CREATE INDEX ON prospeccao.tecnico_carteira(n_fazendas DESC);
CREATE INDEX ON prospeccao.tecnico_carteira(uf);
GRANT SELECT ON prospeccao.tecnico_carteira TO wins_app;
