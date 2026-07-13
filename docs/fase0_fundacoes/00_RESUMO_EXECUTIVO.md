# Resumo executivo

Base analisada: branch `master`, commit `e5b131c5360bb566939f4aa43621c05eec5a70a0`.

**CONFIRMADO NO CÓDIGO:** a sessão usa JWT em cookie (`app/auth.py:64-76`), o pool
é aberto somente sob demanda (`app/db.py:25-31`) e o App de Campo persiste por
`cliente_id` no legado (`app/main.py:4257-5323`). `/fazendas` consulta a base de
prospecção `prospeccao.fazenda_nacional` (`app/main.py:1983`, `2304`).

**IMPLEMENTADO NESTA ETAPA:** um domínio novo `foundation`, sem converter
prospecção nem legado; policies centralizadas e deny-by-default; escopo composto
organização/fazenda; auditoria transacional; catálogo dimensional; parâmetros e
fórmulas versionados; quatro SQL revisáveis e não executados; rota privada
representativa desabilitada por padrão; testes unitários exclusivamente sintéticos.

**DECISÃO:** a Fase 0A prova o padrão para módulos novos. A adoção pelas rotas
existentes será incremental, após inventário e mapeamento de propriedade.

**RISCO:** rotas legadas continuam autenticadas apenas no perímetro e ainda não
possuem isolamento por entidade. Isso não foi ampliado nem corrigido em massa aqui.
