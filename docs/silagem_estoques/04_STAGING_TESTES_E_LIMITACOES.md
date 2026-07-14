# 04 — Staging, Testes e Limitações

## Ambiente de Staging

### Setup

```bash
# 1. Subir ambiente de staging
bash scripts/fase0d/start_staging.sh

# 2. Aplicar migrations do módulo
python scripts/feed_inventory/apply_migrations.py

# 3. Ativar feature flag
# Adicione ao docker-compose.staging.yml:
#   ENABLE_FEED_INVENTORY=true

# 4. Reiniciar containers
docker compose -f docker-compose.staging.yml restart

# 5. Verificar health check
curl http://localhost:8000/api/v1/feed-inventory/dashboard
```

### Aplicando migrations manualmente

```bash
# Conectar ao banco de staging
docker compose -f docker-compose.staging.yml exec db psql -U wins_agro_app -d wins_agro_staging

# Aplicar schema
\i /app/scripts/feed_inventory/migration_001_feed_inventory.sql

# Verificar tabelas
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'storage'
AND table_name LIKE 'feed_%';
```

### Verificação pós-migração

```bash
# Listar tabelas criadas
docker compose exec db psql -U wins_agro_app -d wins_agro_staging -c \
  "SELECT table_name FROM information_schema.tables WHERE table_schema='storage' AND table_name LIKE 'feed_%';"

# Listar índices
docker compose exec db psql -U wins_agro_app -d wins_agro_staging -c \
  "SELECT indexname FROM pg_indexes WHERE schemaname='storage' AND tablename LIKE 'feed_%';"
```

## Executando Testes

### Suite completa

```bash
cd app
python3 -m unittest discover -s tests -p 'test_feed_inventory_*.py' -v
```

### Testes individuais

```bash
# Testes de modelo de dados
python3 -m unittest tests.test_feed_inventory_model -v

# Testes de API
python3 -m unittest tests.test_feed_inventory_api -v

# Testes de regras de negócio
python3 -m unittest tests.test_feed_inventory_rules -v

# Testes de integração com Autonomia Alimentar
python3 -m unittest tests.test_feed_inventory_autonomy -v
```

### Testes HTTP (manuais)

```bash
# Criar instalação
curl -X POST http://localhost:8000/api/v1/feed-inventory/facilities \
  -H "Content-Type: application/json" \
  -d '{"name":"Silo Teste","type":"silo","capacity_kg":100000}'

# Criar lote
curl -X POST http://localhost:8000/api/v1/feed-inventory/lots \
  -H "Content-Type: application/json" \
  -d '{"facility_id":"<UUID>","name":"Lote Teste","type":"silagem","quantity_kg":50000,"dry_matter_pct":35,"total_cost":25000}'

# Registrar entrada
curl -X POST http://localhost:8000/api/v1/feed-inventory/lots/<LOT_ID>/movements \
  -H "Content-Type: application/json" \
  -d '{"type":"entry","quantity_kg":10000,"reference_date":"2026-07-13"}'

# Registrar retirada
curl -X POST http://localhost:8000/api/v1/feed-inventory/lots/<LOT_ID>/movements \
  -H "Content-Type: application/json" \
  -d '{"type":"withdrawal","quantity_kg":5000,"reference_date":"2026-07-13"}'

# Verificar dashboard
curl http://localhost:8000/api/v1/feed-inventory/dashboard

# Verificar fontes para Autonomia
curl http://localhost:8000/api/v1/feed-inventory/autonomy-sources
```

### Resultados dos testes HTTP

| Endpoint | Método | Resultado | Status |
|----------|--------|-----------|--------|
| `/facilities` | GET | Lista vazia返回 | 200 OK |
| `/facilities` | POST | Instalação criada | 201 Created |
| `/facilities/{id}` | GET | Detalhes retornados | 200 OK |
| `/facilities/{id}` | PUT | Atualizada | 200 OK |
| `/facilities/{id}` | DELETE | Removida | 204 No Content |
| `/lots` | GET | Lista vazia返回 | 200 OK |
| `/lots` | POST | Lote criado | 201 Created |
| `/lots/{id}` | GET | Detalhes retornados | 200 OK |
| `/lots/{id}` | PUT | Atualizado | 200 OK |
| `/lots/{id}` | DELETE | Removido | 204 No Content |
| `/lots/{id}/movements` | GET | Lista vazia返回 | 200 OK |
| `/lots/{id}/movements` | POST | Movimentação criada | 201 Created |
| `/movements/{id}` | GET | Detalhes retornados | 200 OK |
| `/dashboard` | GET | Resumo retornado | 200 OK |
| `/reconciliation` | GET | Dados retornados | 200 OK |
| `/autonomy-sources` | GET | Fontes retornadas | 200 OK |
| `/lots/{id}/status` | POST | Status alterado | 200 OK |
| `/losses` | GET | Relatório retornado | 200 OK |
| `/export` | GET | Dados exportados | 200 OK |

## Limitações Conhecidas

### MVP atual

1. **Sem conciliação automática**: a conciliação é apenas visual; não há correção automática
2. **Sem alertas push**: alertas são exibidos apenas no dashboard; sem notificação por email/webhook
3. **Sem histórico de valores**: não há registro de variação de custo ao longo do tempo
4. **Sem suporte a múltiplas moedas**: custos sempre em R$
5. **Sem validação de capacidade**: não impede criação de lote maior que capacidade da instalação
6. **Sem transferência entre instalações**: movimentação de transferência requer dois lançamentos (saída + entrada)
7. **Sem relatórios personalizados**: apenas os endpoints predefinidos
8. **Sem exportação para Excel**: apenas CSV e JSON

## O que NÃO está implementado ainda

### Fase 2

- Alertas por email/webhook
- Transferência direta entre instalações
- Relatórios por período com gráficos
- Conciliação automática com tolerância configurável
- Histórico de variação de custo
- Suporte a múltiplas moedas

### Fase 3

- Integração com balanças para entrada automática
- Rastreabilidade de qualidade (micotoxinas, fermentação)
- Planejamento de compras baseado em consumo
- Integração com ERP para custos
- Dashboard mobile offline
- API pública para integrações externas

### Futuro

- Sensores de temperatura/umidade
- IA para previsão de consumo
- Otimização automática de misturas
- Integração com mercado de commodities
- Blockchain para rastreabilidade
