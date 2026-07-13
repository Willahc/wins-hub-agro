# APIs, jobs e ETL

## APIs internas propostas

Prefixo `/api/v1`; nomes finais podem mudar para aderir ao projeto.

| Domínio | Exemplos | Política |
|---|---|---|
| contexto | `GET /me/organizations`, `GET /farms`, `POST /farms/{id}/select` | sessão + membership |
| estrutura | CRUD `/farms/{farm}/paddocks`, `/fields` | farm editor/admin; geometria versionada |
| alimentação | `/feed/items`, `/feed/movements`, `/feed/balance-runs`, `/feed/scenarios` | ledger idempotente; read-only separado |
| silagem | `/silage-silos`, `/silage-batches`, `/withdrawals` | vínculo farm/batch validado |
| clima | `/farms/{farm}/weather`, `/climate-metrics` | fonte/data/confiança na resposta |
| pasto | `/paddocks/{id}/assessments`, `/vegetation-series` | observado e estimado separados |
| colheita | `/plantings`, `/harvest-plans`, `/resources` | versão otimista |
| grãos | `/grain-units`, `/grain-lots`, `/grain-movements`, `/inspections` | ledger/lote/FIFO |
| regional | `/regional/municipalities/{ibge}`, `/warehouses` | apenas agregado/público permitido |
| alertas | `/alerts`, `/alerts/{id}/dismiss`, `/recommendations` | motivo/auditoria |
| sync | `/sync/batch`, `/sync/status/{key}` | idempotência, limites e ownership |

Erros: `400` sintaxe, `401` sem sessão, `403` sem permissão, `404` também para objeto fora do tenant, `409` conflito/idempotência, `422` campo/unidade, `429` limite, `503` fonte indisponível. Nunca retornar SQL/stack.

## Contrato offline

Cada comando contém `event_uuid`, `idempotency_key`, `device_id`, `captured_at`, timezone/offset, `organization_id` e `farm_id` apenas como alegação a validar, `entity_version` e payload tipado. O servidor deriva o usuário e valida membership vigente.

Resposta por item: `accepted|duplicate|conflict|rejected`, server ID/version, código seguro e campos. O lote pode ter sucesso parcial. Um conflito não bloqueia a fila inteira.

## Pipeline padrão

```text
discover → fetch → raw metadata/checksum → stage → validate → normalize
         → deduplicate → promote transactionally → derive → publish freshness
```

- Raw só é armazenado se licença permitir.
- Staging nunca é consultado pela UI.
- Promoção troca versão/partição de modo atômico.
- Registros desaparecidos não são apagados automaticamente; ficam expirados/inativos conforme fonte.

## Plano por fonte

| Fonte | Periodicidade inicial | Paginação/cache/retenção | Retry/timeout/fallback |
|---|---|---|---|
| SIDRA | verificar nova competência semanal; séries anuais | cache por tabela/período/código; histórico permanente | 3 tentativas; último valor rotulado vencido |
| NASA POWER | diário para células de fazendas ativas; histórico sob demanda | dedupe por célula/data/parâmetro; guardar série normalizada | timeout 30s/backoff; INMET/último dado, sem inventar |
| INMET | horário/diário conforme acesso validado | estação/data/variável/qualidade | fallback POWER marcado como estimado |
| Copernicus | descoberta diária; composição 5–10 dias conforme nuvem | STAC por bbox/data; derivado por versão do polígono | quota/circuit; manter última análise e reduzir confiança |
| INPE | focos em janela operacional; histórico em lote | dedupe satélite+hora+coordenada; TTL curto para alerta | último feed + indicação de atraso |
| SIDRA PAM/PPM | após publicação anual | versionar ano/tabela/classificação | preservar ano anterior |
| MapBiomas | por nova coleção/ano, import manual controlado | hash de arquivo/coleção/classe; histórico | não fazer scraping; versão anterior |
| Conab/SICARM | mensal/trimestral após método validado | snapshot cadastral e `as_of`; nunca vaga real | cadastro vencido visível como tal |
| ZARC | por safra/portaria | snapshot oficial por cultura/município/solo/grupo | bloquear sugestão sem regra vigente |
| SoilGrids | sob demanda por novo polígono/versão | WCS/WebDAV, cache longo | ausência não bloqueia MVP |
| ANA | diário/horário por estações selecionadas | checkpoint por estação/período | credencial/limite; fallback clima |

## Scheduler e concorrência

**PROPOSTA** — processo `worker` separado do `api`, mesma imagem, tabela `job_run` e advisory lock. Um job curto dispara lotes limitados e renova lease; se morrer, outro retoma checkpoint. Não usar cron dentro do worker web.

Limites:

- sem mais de um job por fonte/escopo;
- budget de CPU/memória/disco;
- rate limiter por adapter;
- concorrência baixa e configurável;
- cancelamento e `max_runtime`;
- prioridade tenant ativo > backfill.

## Satélite

1. versão do polígono define chave do produto;
2. STAC descobre cenas, sem baixar raster inteiro;
3. openEO/processamento remoto calcula máscara e estatísticas por polígono;
4. guardar metadados, percentis, pixels válidos, cenas e algoritmo;
5. opcionalmente guardar thumbnail/recorte pequeno autorizado;
6. recalcular apenas quando houver cena adequada ou mudança de polígono/algoritmo.

**RISCO** — mosaico nacional/COGs na VPS pode esgotar disco/RAM e competir com PostgreSQL. Scripts atuais provam viabilidade exploratória, não desenho de produção.

## Qualidade e observabilidade

Cada run registra contagem lida/válida/rejeitada/inserida/atualizada, bytes, duração, checkpoint, versão de schema e idade. Métricas e alertas:

- `source_freshness_seconds` por dataset;
- taxa de faltantes/outliers/duplicados;
- quebra de schema;
- retry/dead-letter;
- quota/crédito restante quando disponível;
- divergência grande versus versão anterior;
- disco e duração de promoção.

## Segurança de adapters

- allowlist de hosts e HTTPS;
- segredo em variável/secret, nunca banco/log/documento;
- proteção SSRF: usuário não fornece URL;
- limite de tamanho/descompressão e validação MIME/schema;
- checksums, nomes internos e diretório não executável;
- sanitizar CSV/planilha em exportação;
- licença/atribuição mantida até UI/PDF.

## Idempotência e revisão

Chave recomendada: `adapter:dataset_version:scope:period:external_key`. Importação revisada cria nova versão e marca supersessão; não altera silenciosamente um cálculo já publicado. Runs dependentes podem ser marcados “fonte revisada” e recalculados, preservando original.
