# Modelo de dados conceitual

Não é migration. Tipos são conceituais (`uuid`, `numeric`, `date`, `timestamptz`, `jsonb`, geometria) e devem ser refinados após o spike e o inventário do schema real.

## Convenções obrigatórias

Toda entidade privada contém `organization_id`, escopo de fazenda quando aplicável, `created_by`, `created_at`, `updated_by`, `updated_at` e `version`. Exclusão operacional usa estado/arquivamento; eventos, cálculos e movimentos não são apagados. FKs e policies no serviço validam o mesmo tenant.

Classificação de valor:

- `USER_REPORTED`: informado pelo usuário;
- `OBSERVED`: observado/medido em campo ou sensor;
- `IMPORTED_OFFICIAL`: importado de fonte oficial;
- `FORECAST`: previsão;
- `ESTIMATED`: estimativa/modelo remoto;
- `DERIVED`: calculado;
- `BENCHMARK`: comparação agregada.

Todo valor externo/calculado deve apontar para `source_record`/`formula_run`, com unidade e instante de validade.

## Identidade, propriedade e estrutura rural

| Entidade/objetivo | Campos principais (tipo/unidade/obrig.) | Relações, constraints e índices | Origem, histórico e retenção |
|---|---|---|---|
| `organization` — tenant | id uuid O; nome text O; status enum O; timezone default | nome não concede identidade; índice status | usuário/admin; manter enquanto contrato/legal |
| `user` — identidade | id uuid O; email citext O; status; auth_subject | email unique normalizado | sistema de identidade; eventos de status retidos |
| `membership` — papel | organization_id/user_id O; role; farm_scope; valid_from/to | unique org+user+scope; negar por padrão | admin; histórico temporal/auditoria |
| `farm` — propriedade operacional | id; organization_id O; nome O; código; município_ibge; timezone; status | unique org+código; índice org+status/município | usuário; não confundir com lead/CAR |
| `farm_boundary` — limite | farm_id O; geometry/GeoJSON O; area_ha D; valid_from/to; precision/source | geometria válida; uma versão vigente; índice espacial/bbox | usuário/importado; versões permanentes |
| `production_unit` — subdivisão gerencial | farm_id O; nome O; finalidade; status | unique farm+nome ativo | usuário; histórico de status |
| `field` — talhão | unit_id/farm_id O; nome; geometry; area_ha; uso | containment/overlap como warning; índice espacial | usuário; versões permanentes |
| `paddock` — piquete | farm_id/unit_id; nome O; geometry O; area_ha D; capacidade_ref opcional | unique farm+nome ativo; geometria válida | usuário; histórico espacial |

`O` significa obrigatório. Área calculada não substitui área declarada: guardar ambas e a diferença.

## Produção agrícola e campo

| Entidade | Campos principais | Relações/índices/constraints | Origem/histórico/retenção |
|---|---|---|---|
| `crop` | código, nome, finalidade, unidade padrão | catálogo versionado | referência; permanente |
| `cultivar` | crop_id, nome, grupo/ciclo, fonte | unique por fonte+versão | oficial/usuário; versionado |
| `crop_season` | farm_id, nome/safra, início/fim, status | unique farm+nome | usuário; permanente |
| `planting` | field_id, season_id, crop/cultivar, area_ha, datas plantio/emergência, finalidade, produtividade esperada | datas coerentes; índice farm+season+status | informado; permanente |
| `harvest` | planting_id, datas, area, massa/produção, umidade, destino, status | unidade/base de umidade obrig.; índice planting+date | observado/informado; permanente |
| `field_observation` | entidade alvo, tipo, valor/unidade, classe, nota, foto, occurred_at, localização, confidence | alvo pertence à farm; índice farm+target+occurred_at | observado offline; retenção contratual |
| `machine_resource` | farm/org, tipo, capacidade, largura, velocidade, disponibilidade, custo/h | ranges positivos | informado; histórico temporal |
| `transport_resource` | capacidade_t, quantidade, ciclo_min, custo, proprietário | base/unidade obrig.; índice org+status | informado/Log; histórico |
| `harvest_plan` | planting, janela, cenários, capacidades, status, formula_run | version optimistic; índice farm+window | derivado + snapshot permanente |

## Clima, fontes e satélite

| Entidade | Campos principais | Relações/índices/constraints | Origem/histórico/retenção |
|---|---|---|---|
| `data_source` | código, instituição, dataset, versão, licença_url, classe, granularidade, termos_revisados_em | unique instituição+dataset+versão | catálogo interno; permanente |
| `source_record` | source_id, external_key, fetched_at, valid_time, payload_hash, status, quality, raw_ref | unique source+external_key+version; não guardar payload proibido | importado; conforme licença/auditoria |
| `weather_station` | source, external_id, nome, lat/lon, altitude, tipo, timezone, ativo | unique source+external_id; spatial/bbox | oficial; histórico de metadados |
| `weather_observation` | station/grid, variable, value, unit, observed_at, quality | unique source+point+variable+time; índice time | observado/importado; série de longo prazo |
| `weather_forecast` | issue_at, valid_at, horizon, point/grid, variable/value/unit, model | unique model+run+point+var+valid | previsão; preservar runs para avaliar erro |
| `climate_metric` | farm/geometry, período, métrica, valor/unidade, formula_run/confidence | unique scope+metric+period+version | derivado; série permanente |
| `satellite_scene` | source, mission, item_id, acquired_at, cloud, footprint, asset refs | unique source+item; índice spatial/time | metadado importado; assets por política |
| `vegetation_index` | paddock/field, index_type, period, value/stats, valid_pixels, cloud_mask, scene refs, confidence | unique geometry-version+index+period+algorithm | estimado; manter série e versão |
| `imagery_derivative` | geometry, algorithm_version, bbox, storage_ref, checksum, expires | storage autorizado; unique checksum | derivado; recortes retidos por política |

## Rebanho e alimentação

`fazenda.cliente`, grupo, animal e pesagem atuais serão mapeados; não duplicar sem plano de migração.

| Entidade | Campos principais | Relações/índices/constraints | Origem/histórico/retenção |
|---|---|---|---|
| `animal_lot` | farm_id, nome, categoria, cabeça atual, peso médio, paddock atual | pode referenciar grupo atual; índice farm+status | informado/derivado de animais; temporal |
| `feed_requirement` | lot_id, heads, avg_weight_kg, intake_pct_bw, dm_demand_kg_day, as_of, formula_run | valores positivos e snapshot | derivado; cada cálculo preservado |
| `pasture_assessment` | paddock, date, method, forage_mass_kg_dm_ha, height_cm, utilization, observer, confidence | método/unidades obrig.; índice paddock+date | observado/estimado separados; permanente |
| `forage_availability` | scope, period, gross_dm_kg, usable_dm_kg, recovery_days, formula_run | não somar períodos incompatíveis | derivado; permanente |
| `feed_item` | farm, category(silage/hay/concentrate/pasture), nome, unit, dm_pct, cost_basis, active | unique farm+nome ativo | usuário/catálogo; histórico |
| `feed_stock_location` | farm, type, silo/storage ref, nome | um local por escopo; status | usuário; permanente |
| `feed_stock_movement` | location/item, type(in/out/adjust/loss/transfer), quantity, unit, dm_snapshot, occurred_at, idempotency_key, reference | unique org+idempotency; transfer balanced; índice location+date | observado/informado; imutável/retido |
| `feed_balance_run` | farm/scope, horizon, scenario, inputs snapshot, demand, supply, deficit, autonomy, rupture_date, confidence, formula_version | hash de entradas; índice farm+created_at | derivado; permanente |
| `scenario` | farm, base_run, nome, changes json validado, owner, status | não altera operação sem apply | usuário; retenção contratual |

## Silagem e silos

| Entidade | Campos principais | Relações/índices/constraints | Origem/histórico/retenção |
|---|---|---|---|
| `silage_silo` | farm, nome, tipo, coordenada, dimensões m, geometry_profile, status | dimensões >0; unique farm+nome ativo | usuário; histórico de alteração |
| `silage_batch` | silo, crop/cultivar/planting, cut/close/open dates, green_mass_kg, dm_pct, density_kg_m3, inoculant, expected_loss_pct, cost | base e unidade obrigatórias; datas coerentes | informado/observado; permanente |
| `silage_measurement` | batch, date, face/dimensions, mass estimate, dm, compaction, method, confidence | índice batch+date | observado/estimado; permanente |
| `silage_withdrawal` | batch, lot/destination, green kg, dm kg, date, idempotency | ledger/movement pareado | observado offline; imutável |
| `hay_batch` | farm/location, crop, bales, avg_weight, dm, date, loss, cost | lote rastreável | informado; até expiração + auditoria |

## Grãos e armazenagem

| Entidade | Campos principais | Relações/índices/constraints | Origem/histórico/retenção |
|---|---|---|---|
| `grain_storage_unit` | farm/org, nome, tipo, capacidade nominal/útil t, coordenada, status | útil ≤ nominal; unique org+nome | usuário; histórico |
| `grain_lot` | storage, crop/product, season, source, entry_date, weight, moisture, impurity, classification, value | unidade/base obrig.; índice storage+product+date | observado/informado; permanente |
| `grain_movement` | lot/from/to, entrada/saída/transfer/adjust/loss, weight, moisture, occurred_at, idempotency | transferência balanceada; saldo ≥ regra | imutável; permanente |
| `grain_inspection` | unit/lot, temperature, moisture, sanitary status, finding, attachment, date | ranges e sensor/método | observado; permanente |
| `drying_event` | lot, in/out weight/moisture, energy/cost, start/end | balanço e base de umidade | observado; permanente |
| `aeration_event` | unit/lot, start/end, temperature, reason, result, cost | fim ≥ início | observado; permanente |
| `storage_loss` | lot, quantity, reason, method, estimated/observed, value, formula_run | classe obrigatória | observado/estimado separados; permanente |

## Regional, alertas e integração

| Entidade | Campos principais | Relações/índices/constraints | Origem/histórico/retenção |
|---|---|---|---|
| `external_warehouse` | source, external_id, nome, município, coordinates, type/services, registered_capacity, updated_at | unique source+external_id; spatial | importado/colaborativo; versionado |
| `warehouse_availability` | warehouse, capacity/free, confirmed_at, expires_at, confirmation_source | só exibir vigente; classe E | fornecedor; curta retenção + histórico |
| `municipal_indicator` | ibge_code, year, metric, value/unit, source/version | unique code+year+metric+source | oficial/benchmark; permanente |
| `regional_storage_indicator` | region/year, production, static_capacity, ratio/gap, formula_run | rotular teórico | derivado; permanente |
| `alert_rule` | organization/system, code, version, inputs, threshold, severity, message template, active | unique org+code+version | especialista/admin; versionado |
| `alert_instance` | rule, entity, observed/threshold, source, confidence, triggered_at, reevaluate_at, status/dismiss_reason | dedupe key; índice org+status+severity | derivado; permanente/auditoria |
| `recommendation` | alert/run, text, evidence, confidence, action, disclaimer, version | sem ordem automática irreversível | derivado/revisado; permanente |
| `formula_definition` | code, version, category, expression/implementation_ref, units, sources, approved_by/at, status | unique code+version; imutável publicada | especialista; permanente |
| `formula_parameter` | formula/version, scope, key, value/unit, valid_from/to, source, confidence | intervalo sem sobreposição | configurado; temporal |
| `formula_run` | formula/version, scope, inputs/output snapshot, units, confidence, executed_at | hash/reprodutível | sistema; permanente |
| `audit_event` | org, actor, action, resource, before/after redigido, request/idempotency, occurred_at | append-only; índice org+resource/time | sistema; política legal |
| `integration_outbox` | event_id/type/version, tenant, payload_ref, status/attempts | unique event; sem PII excessiva | sistema; até entrega + auditoria |
| `job_run` | source/job, scope, checkpoint, status, attempts, metrics, error_code, started/ended | lock/dedupe | sistema; retenção operacional |

## Constraints transversais

- `numeric` para massa, área, percentual e dinheiro; nenhum `float` para saldo/custo.
- unidade não é texto livre: catálogo UCUM/interno e conversões testadas.
- percentuais têm faixa `[0,100]`; confiança `[0,1]`; datas coerentes.
- FK composta ou validação equivalente impede referência cruzada entre tenants.
- saldo não é campo editável: view/agregado do ledger, com snapshot para performance.
- anexos têm hash, MIME/tamanho, owner e autorização.
- retenção final depende de contrato/LGPD/legislação fiscal; “permanente” aqui significa histórico de negócio, não decisão legal.
