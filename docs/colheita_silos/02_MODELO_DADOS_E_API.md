# Modelo de dados e API

Tabelas:

- `harvest.harvest_plans`: cronograma, totais previstos e reais, status e chave de conclusão.
- `harvest.harvest_plan_areas`: área, cultura, produtividade e resultados calculados.
- `harvest.harvest_storage_allocations`: vínculo com estrutura, snapshots de capacidade e lote criado.

IDs internos nunca fazem parte do contrato HTTP. Todos os recursos são resolvidos por UUID e validados no contexto organização/fazenda.

Endpoints sob `/api/v2/farms/{farm_uuid}/harvest-silos`:

- `GET /dashboard`
- `POST /simulate`
- `POST|GET /plans`
- `GET|PUT|DELETE /plans/{plan_uuid}`
- `POST /plans/{plan_uuid}/start`
- `POST /plans/{plan_uuid}/complete`

Ao concluir, a mesma transação cria `storage.feed_lots`, registra `storage.feed_stock_movements` como `initial_balance`, liga cada alocação ao lote e marca o plano como concluído.
