# Fontes de dados gratuitas

## Classificação

- **A:** API aberta, automação direta.
- **B:** gratuita, exige conta/token.
- **C:** download público ou processo parcialmente manual.
- **D:** informação pública, automação incerta.
- **E:** parceria/atualização do fornecedor.
- **F:** não recomendada para a primeira versão.

Validação em 13/07/2026. “Gratuita” não significa SLA, uso ilimitado ou redistribuição irrestrita.

## Matriz

| Fonte/classificação | Dado/cobertura/granularidade | Acesso, autenticação e limite | Atualização/licença/custo | Uso, cache, risco e fallback | Situação |
|---|---|---|---|---|---|
| INMET — **C/D** | estações Brasil; observações diárias/horárias e históricos | BDMEP/portal e downloads; API pública estável, contrato e limites não foram confirmados | horários em UTC; licença/redistribuição comercial por dataset precisam confirmação | fonte observada prioritária; cache permanente por estação/data; fallback NASA POWER | **VALIDAÇÃO EXTERNA PENDENTE** para automação e licença. [BDMEP](https://portal.inmet.gov.br/servicos/bdmep-dados-hist%C3%B3ricos) |
| NASA POWER — **A** | grade global por ponto; meteorologia ~0,5°×0,625°, solar ~1°; diário/horário/mensal | REST sem token demonstrado; fair use, evitar paralelismo excessivo | dados meteorológicos podem ser substituídos por qualidade melhor em 2–3 meses; gratuito | fallback/normal climático, não “estação da fazenda”; cache por célula/parâmetro/período | **VALIDADO TECNICAMENTE**; termos/licença do dataset ainda devem constar no registro de fonte. [API](https://power.larc.nasa.gov/docs/tutorials/service-data-request/api/) |
| Copernicus Data Space — **B** | Sentinel-1/2 e catálogo global; cena/pixel | STAC para descoberta; downloads/processamento exigem fluxos CDSE; openEO exige conta e usa créditos | conta geral recebe cota gratuita de openEO, sujeita a política vigente | processar só polígonos ativos; cache de índice/agregado, não cenas na VPS; fallback observação de campo/MapBiomas | **VALIDADO TECNICAMENTE**, custo e licença de resultados por fluxo devem ser validados. [STAC](https://documentation.dataspace.copernicus.eu/APIs/STAC.html), [créditos openEO](https://documentation.dataspace.copernicus.eu/APIs/openEO/credit_usage.html) |
| IBGE SIDRA — **A** | PAM/PPM e séries municipais/UF | API REST sem token já usada no projeto | periodicidade depende da pesquisa, em geral anual; dados oficiais | inteligência municipal/produção/rebanho; cache por tabela/período/código | **CONFIRMADO NO CÓDIGO** em `app/external_apis.py`, linhas 1–165; validar metadados e licença de cada tabela. [API SIDRA](https://apisidra.ibge.gov.br/) |
| MAPA/ZARC — **C/D** | município, cultura, grupo de cultivar, solo, ciclo e janela de risco | portal/painel/CSV; catálogo informa API do portal CKAN, mas dataset de cultivares estava “em manutenção” na consulta | publicação por safra/portaria; licença e estabilidade do recurso precisam confirmação | regra oficial versionada por safra; nunca previsão meteorológica | **VALIDAÇÃO EXTERNA PENDENTE**. [Dados Abertos MAPA](https://dados.agricultura.gov.br/dataset?tags=zarc) |
| Conab/SICARM — **C/D** | unidades cadastradas, localização/tipo e capacidade estática; Brasil | consulta pública; não foi confirmada API estável/documentada para extração em lote | atualização cadastral heterogênea; cadastro não é ocupação | mapa/radar regional; armazenar data/fonte; fallback cadastro colaborativo validado | **VALIDAÇÃO EXTERNA PENDENTE** para automação/licença. [SICARM](https://sisdep.conab.gov.br/consultaarmazem/?page=Sobre) |
| OpenStreetMap — **A/C** | vias e POIs globais; granularidade colaborativa | dados ODbL; tiles públicos são best-effort e proíbem bulk/offline | atualização contínua; atribuição e share-alike conforme ODbL | mapa/POIs; usar provedor compatível ou tiles próprios para escala/offline; não inferir serviço/capacidade | **VALIDADO**. [licença](https://www.openstreetmap.org/copyright), [política de tiles](https://operations.osmfoundation.org/policies/tiles/) |
| INPE Queimadas — **A/C** | focos, eventos, área queimada e risco; Brasil/América do Sul | downloads CSV/KML/TIFF/Shapefile; sem token demonstrado | focos quase reais até 10 min; evento provisório pode estar em validação | alerta regional e proximidade; cache por janela e deduplicação; não prova incêndio dentro do piquete | **VALIDADO PARA DOWNLOAD**, licença/limite de automação deve ser registrado. [dados abertos](https://terrabrasilis.dpi.inpe.br/queimadas/portal/pages/secao_downloads/dados-abertos/) |
| MapBiomas — **C/B** | cobertura/uso/pastagem e séries históricas; Brasil | planilhas/rasters/plataformas; Alerta possui GraphQL, mas não é a mesma coleção de cobertura | versão por coleção/ano; atribuição/termos variam por produto | baseline/benchmark e histórico; cache versionado; não usar classe modal como diagnóstico | **CONFIRMADO NO CÓDIGO** que há ingestão local; **VALIDAÇÃO EXTERNA PENDENTE** para licença e método oficial de cada produto. [API Alerta](https://plataforma.alerta.mapbiomas.org/api/docs/index.html) |
| Embrapa GeoInfo — **C/D** | catálogos geoespaciais variados, cobertura por dataset | WMS/WFS/WCS/CSW oficiais | periodicidade/licença por camada, sem SLA geral confirmado | solo/zoneamento como fonte específica; cache e atribuição por metadado | **VALIDADO TECNICAMENTE**, seleção/licença por camada pendente. [desenvolvedores](https://geoinfo.dados.embrapa.br/developer/) |
| SoilGrids/ISRIC — **C** | propriedades estimadas do solo, grade global | WCS/WebDAV/WMS; REST beta está temporariamente pausada; fair use informado de 5 req/min quando disponível | CC BY 4.0; sem SLA | covariável/estimativa, não análise de laboratório; usar WCS por recorte, cache longo | **VALIDADO**, REST **não recomendada**. [acesso/licença](https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_02.html) |
| ANA/HidroWeb — **B/C** | chuva, nível, vazão e estações; Brasil | API oficial requer solicitação e credencial; séries têm limites específicos por operação | dados abertos com atribuição; atualização por rede/estação | complementar hidrologia/chuva; cache por estação/data; fallback INMET/POWER | **VALIDADO TECNICAMENTE**, credencial e termos operacionais pendentes. [manual](https://www.gov.br/ana/pt-br/assuntos/monitoramento-e-eventos-criticos/monitoramento-hidrologico/orientacoes-manuais/manuais/manual-hidrowebservice_publica.pdf/view), [acesso](https://www.snirh.gov.br/hidroweb/acesso-api) |
| Estados/municípios — **D/F** | cobertura variável | portal/arquivo/API não padronizados | licença/atualização variáveis | aceitar somente adapter por fonte documentada e cobertura relevante | **VALIDAÇÃO EXTERNA PENDENTE** por fonte. |
| Disponibilidade real de armazém — **E** | vaga, fila, tarifa, recebimento | integração/confirmacão do fornecedor | frequência contratual | mostrar somente com timestamp e confirmação | parceria necessária; não derivar do SICARM. |

## Ficha operacional consolidada

O custo direto indicado abaixo é o do acesso ao dado segundo a documentação encontrada, não o custo de infraestrutura, engenharia, egress, processamento ou suporte.

| Fonte | Método/auth/limite | Licença e redistribuição | Confiabilidade e custo direto | Cache/uso/fallback |
|---|---|---|---|---|
| INMET | portal/BDMEP; autenticação e limites de API não confirmados | **pendente por dataset** | instituição oficial; continuidade de automação não confirmada; R$0 no portal | histórico por estação; clima observado; POWER marcado como grade |
| NASA POWER | REST, token não exigido nos exemplos; fair use sem número fixo publicado na página consultada | registrar termos/atribuição antes de produção | NASA, grade/modelo global e revisão posterior; R$0 | célula/parâmetro/data; fallback climático, nunca estação local |
| Copernicus CDSE | STAC aberto para catálogo; conta/OIDC nos serviços de processamento; openEO com créditos | termos/licença variam por produto/serviço | programa oficial, mas quota e serviço podem mudar; cota gratuita, excedente/infra pendentes | metadado/cena/derivado por polígono; campo/última composição |
| IBGE SIDRA | REST, sem token no uso atual; limites formais não localizados nesta revisão | dados oficiais; confirmar termos gerais/atribuição | alta para indicador oficial conforme metodologia; R$0 | tabela/período/município; versão anterior com ano visível |
| MAPA/ZARC | arquivo/painel/CKAN; estabilidade do recurso/API pendente | portaria/dado público, redistribuição e recurso precisam revisão | oficial para regra publicada, não forecast; R$0 | safra/cultura/município/solo/grupo; bloquear se regra ausente |
| Conab/SICARM | consulta pública; API/bulk/limite não confirmados | uso/redistribuição do cadastro pendentes | oficial para cadastro, recência por unidade variável; R$0 na consulta | snapshot/data; cadastro colaborativo validado, sem inferir vaga |
| OpenStreetMap | download/serviços; dados sem conta; tiles com política e sem SLA | ODbL, atribuição/share-alike; tiles sob policy | colaborativa e variável; dados R$0, serviço de tiles próprio/provedor custa infraestrutura | cache de dados conforme ODbL; tiles conforme headers; provedor alternativo |
| INPE Queimadas | downloads diretos, sem token demonstrado; limites de automação não localizados | atribuição/termos específicos ainda devem ser registrados | oficial; focos são detecção remota e eventos podem ser provisórios; R$0 | janela temporal/dedupe; último feed com atraso explícito |
| MapBiomas | downloads/plataformas/GEE; conta depende do canal; Alerta GraphQL não substitui cobertura | termos variam por produto/coleção; **pendente** | referência amplamente usada, mas estimativa/classificação; R$0, processamento pode ter quota/custo | coleção/ano/classe; campo/dado anterior |
| Embrapa GeoInfo | OGC WMS/WFS/WCS/CSW; auth/limite por camada não confirmados | licença por camada/metadado | instituição oficial, heterogênea por dataset; R$0 quando aberto | recorte/camada/versão; fonte alternativa específica |
| SoilGrids | WCS/WebDAV/WMS anônimo; REST beta pausada (fair use publicado: 5 req/min quando ativa) | CC BY 4.0 | modelo global estimado, sem SLA; R$0 | recorte/propriedade/versão; ausência não bloqueia MVP |
| ANA/HidroWeb | REST com credencial solicitada; limites por operação (ex.: algumas séries até 366 dias) | dados abertos/atribuição; observar manual/termos | rede oficial, qualidade/cobertura por estação; R$0 após autorização | estação/variável/período; INMET/POWER rotulado |
| Estados/municípios | caso a caso | caso a caso | não presumida; custo oculto de manutenção alto | somente adapter aprovado; fonte federal ou entrada manual |

**VALIDAÇÃO EXTERNA PENDENTE** — limites não publicados não significam “sem limite”. O adapter deve ser conservador até confirmação formal.

## Seleção recomendada por fase

1. **MVP:** nenhuma dependência externa obrigatória; SIDRA apenas benchmark opcional.
2. **Clima:** INMET observado quando operacionalmente validado + NASA POWER como grade/fallback; ANA apenas onde agregar valor.
3. **Pasto Vivo:** Copernicus recortado + observação de campo; MapBiomas como histórico/base.
4. **Colheita:** clima + ZARC versionado; ZARC não substitui maturidade observada.
5. **Radar:** SIDRA PAM + Conab/SICARM, ambos com ano/data; indicador sempre “teórico”.
6. **Logística:** OSM para rede/POIs, provedor de rota ou motor próprio a decidir; tile público OSM não suporta offline/prefetch.

## Checklist antes de ativar qualquer adapter

- salvar URL/documentação, dataset, versão, licença, atribuição e data da revisão;
- confirmar uso comercial, armazenamento, cache e redistribuição;
- criar amostra com valores faltantes, unidades, timezone e códigos geográficos;
- definir timeout, rate limit, User-Agent, backoff e contato;
- testar mudança de schema, indisponibilidade e dado revisado;
- registrar hash/payload bruto permitido, `observed_at`, `published_at`, `ingested_at`;
- garantir que fonte estimada não sobrescreva dado observado/informado.

## Fontes não recomendadas no primeiro corte

- scraping de páginas sem termo e contrato técnico;
- tiles comunitários OSM para cache offline ou carga massiva;
- API REST SoilGrids beta pausada;
- Earth Engine como dependência única sem confirmar conta, quota e uso comercial;
- qualquer endpoint “descoberto” por inspeção de navegador sem documentação oficial.
