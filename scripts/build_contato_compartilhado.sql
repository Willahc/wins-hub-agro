-- build_contato_compartilhado.sql
-- Números de WhatsApp compartilhados por >=3 DECISORES distintos = sinal de
-- central/contador/escritório (não é o contato de um produtor específico).
-- Usado para REBAIXAR o badge verde "WhatsApp verificado" nas páginas (mesmo
-- número aparecendo em vários leads distintos não é contato confiável daquele lead).
-- Nota: multi-CNPJ do MESMO dono tem 1 decisor distinto -> NÃO entra (legítimo).
-- Idempotente.
DROP TABLE IF EXISTS prospeccao.contato_compartilhado;
CREATE TABLE prospeccao.contato_compartilhado AS
SELECT regexp_replace(whatsapp, '\D', '', 'g') AS fone,
       count(DISTINCT decisor) AS n_decisores
FROM prospeccao.lead_demanda
WHERE whatsapp IS NOT NULL AND whatsapp <> ''
  AND decisor IS NOT NULL AND decisor <> ''
GROUP BY 1
HAVING count(DISTINCT decisor) >= 3;
ALTER TABLE prospeccao.contato_compartilhado ADD PRIMARY KEY (fone);

SELECT count(*) AS numeros_compartilhados, sum(n_decisores) AS soma_decisores
FROM prospeccao.contato_compartilhado;
