# Autonomia Alimentar — Contrato da API

## Endpoints

### POST /api/v2/farms/{farm_uuid}/food-autonomy/simulate

Calcula autonomia sem persistir.

**Entrada:**
```json
{
  "name": "Cenário seca 2026",
  "reference_date": "2026-07-01",
  "target_days": 90,
  "safety_margin_pct": "10",
  "herd": [
    {"category": "lactating_cows", "head_count": 20,
     "average_weight_kg": "450", "intake_pct_body_weight": "2.5"}
  ],
  "pastures": [
    {"name": "Piquete Norte", "area_ha": "10",
     "available_dm_kg_ha": "2000", "utilization_pct": "50"}
  ],
  "feeds": [
    {"feed_type": "silage", "name": "Silo",
     "quantity_natural_kg": "10000", "dry_matter_pct": "35",
     "utilization_pct": "90"}
  ]
}
```

**Saída:**
```json
{
  "formula_version": "food_autonomy.v1",
  "daily_demand_dm_kg": "225.00",
  "pasture_usable_dm_kg": "10000.00",
  "stored_feed_usable_dm_kg": "3150.00",
  "physical_total_dm_kg": "13150.00",
  "reserve_dm_kg": "1315.00",
  "planning_available_dm_kg": "11835.00",
  "autonomy_days": "52.60",
  "target_days": 90,
  "target_required_dm_kg": "20250.00",
  "balance_dm_kg": "-8415.00",
  "balance_days": "-37.40",
  "status": "warning",
  "estimated_end_date": "2026-09-03",
  "warnings": ["Estimativa baseada nos dados informados."]
}
```

### POST /api/v2/farms/{farm_uuid}/food-autonomy/scenarios

Cria e persiste um cenário. Recalcula no servidor.

### GET /api/v2/farms/{farm_uuid}/food-autonomy/scenarios

Lista cenários da fazenda. Paginação: `limit` (1–100), `offset`.

### GET /api/v2/farms/{farm_uuid}/food-autonomy/scenarios/{scenario_uuid}

Retorna cenário completo com itens.

### PUT /api/v2/farms/{farm_uuid}/food-autonomy/scenarios/{scenario_uuid}

Atualiza cenário (recalcula no servidor).

### DELETE /api/v2/farms/{farm_uuid}/food-autonomy/scenarios/{scenario_uuid}

Arquivamento lógico.

## Headers

Todas as respostas autenticadas incluem:
```
Cache-Control: no-store, private
Pragma: no-cache
X-Content-Type-Options: nosniff
```

## Erros

- 401: Não autenticado
- 403: Sem permissão
- 404: Recurso não encontrado (cross-tenant)
- 422: Validação

## Validações

- Quantidade de animais: ≥ 0, inteiro
- Peso: > 0
- Consumo: > 0, ≤ 10%
- Área: > 0
- MS/ha: ≥ 0
- Percentuais: 0–100
- Meta: ≥ 1 dia
- Cenário: ≥ 1 item de rebanho, ≥ 1 fonte de alimento
