# 02 — Modelo de Dados e API

## Schema

Todas as tabelas do módulo residem no schema `storage`.

## Tabelas

### feed_storage_facilities

Instalações de armazenamento de insumos.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID | Chave primária |
| `farm_id` | UUID | FK → fazenda |
| `name` | TEXT NOT NULL | Nome da instalação |
| `type` | TEXT NOT NULL | Tipo: silo, bunker, cocho, deposito, outro |
| `capacity_kg` | NUMERIC | Capacidade máxima em kg |
| `capacity_m3` | NUMERIC | Capacidade máxima em m³ |
| `location_description` | TEXT | Descrição da localização |
| `status` | TEXT DEFAULT 'active' | active, inactive, maintenance |
| `created_at` | TIMESTAMPTZ DEFAULT now() | Data de criação |
| `updated_at` | TIMESTAMPTZ DEFAULT now() | Data de atualização |

**Índices:**
- `idx_feed_facilities_farm` ON (farm_id)
- `idx_feed_facilities_type` ON (type)

**Constraints:**
- `pk_feed_storage_facilities` PRIMARY KEY (id)
- `fk_feed_facilities_farm` FOREIGN KEY (farm_id) REFERENCES fazenda(id)

---

### feed_lots

Lotes de insumos armazenados.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID | Chave primária |
| `facility_id` | UUID | FK → feed_storage_facilities |
| `farm_id` | UUID | FK → fazenda |
| `name` | TEXT NOT NULL | Nome/identificação do lote |
| `type` | TEXT NOT NULL | Tipo: silagem, feno, concentrado, mistura, outro |
| `quantity_kg` | NUMERIC NOT NULL DEFAULT 0 | Quantidade atual em kg |
| `dry_matter_pct` | NUMERIC DEFAULT 0 | Percentual de matéria seca |
| `contamination_pct` | NUMERIC DEFAULT 0 | Percentual de contaminação |
| `total_cost` | NUMERIC DEFAULT 0 | Custo total (R$) |
| `cost_per_kg` | NUMERIC DEFAULT 0 | Custo por kg (calculado) |
| `cost_per_kg_ms` | NUMERIC DEFAULT 0 | Custo por kg de MS (calculado) |
| `daily_consumption_kg` | NUMERIC DEFAULT 0 | Consumo diário estimado em kg |
| `days_remaining` | NUMERIC DEFAULT 0 | Dias restantes estimados |
| `estimated_end_date` | DATE | Data fim estimada |
| `loss_pct` | NUMERIC DEFAULT 0 | Percentual de perda acumulada |
| `loss_value` | NUMERIC DEFAULT 0 | Valor monetário da perda (R$) |
| `status` | TEXT DEFAULT 'available' | available, reserved, opened, depleted, quarantined, archived |
| `harvest_date` | DATE | Data de colheita/recebimento |
| `notes` | TEXT | Observações |
| `created_at` | TIMESTAMPTZ DEFAULT now() | Data de criação |
| `updated_at` | TIMESTAMPTZ DEFAULT now() | Data de atualização |

**Índices:**
- `idx_feed_lots_facility` ON (facility_id)
- `idx_feed_lots_farm` ON (farm_id)
- `idx_feed_lots_type` ON (type)
- `idx_feed_lots_status` ON (status)

**Constraints:**
- `pk_feed_lots` PRIMARY KEY (id)
- `fk_feed_lots_facility` FOREIGN KEY (facility_id) REFERENCES feed_storage_facilities(id)
- `fk_feed_lots_farm` FOREIGN KEY (farm_id) REFERENCES fazenda(id)

---

### feed_stock_movements

Movimentações de estoque (ledger imutável).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID | Chave primária |
| `lot_id` | UUID | FK → feed_lots |
| `farm_id` | UUID | FK → fazenda |
| `type` | TEXT NOT NULL | Tipo da movimentação |
| `quantity_kg` | NUMERIC NOT NULL | Quantidade movimentada (positiva para entradas, negativa para retiradas) |
| `dry_matter_pct` | NUMERIC | MS informada no momento da movimentação |
| `cost_total` | NUMERIC | Custo total informado |
| `loss_pct` | NUMERIC | Percentual de perda (apenas para type=loss) |
| `loss_reason` | TEXT | Motivo da perda (código do enum) |
| `reference_date` | DATE NOT NULL | Data de referência da movimentação |
| `notes` | TEXT | Observações |
| `created_by` | TEXT | Usuário que criou a movimentação |
| `created_at` | TIMESTAMPTZ DEFAULT now() | Data de criação |
| `immutable` | BOOLEAN DEFAULT true | Sempre true — movimentações são imutáveis |

**Índices:**
- `idx_feed_movements_lot` ON (lot_id)
- `idx_feed_movements_farm` ON (farm_id)
- `idx_feed_movements_type` ON (type)
- `idx_feed_movements_reference` ON (reference_date)

**Constraints:**
- `pk_feed_stock_movements` PRIMARY KEY (id)
- `fk_feed_movements_lot` FOREIGN KEY (lot_id) REFERENCES feed_lots(id)
- `fk_feed_movements_farm` FOREIGN KEY (farm_id) REFERENCES fazenda(id)

---

## Endpoints da API

Base path: `/api/v1/feed-inventory`

| # | Método | Path | Descrição |
|---|--------|------|-----------|
| 1 | GET | `/facilities` | Listar instalações |
| 2 | POST | `/facilities` | Criar instalação |
| 3 | GET | `/facilities/{id}` | Detalhar instalação |
| 4 | PUT | `/facilities/{id}` | Atualizar instalação |
| 5 | DELETE | `/facilities/{id}` | Remover instalação |
| 6 | GET | `/lots` | Listar lotes |
| 7 | POST | `/lots` | Criar lote |
| 8 | GET | `/lots/{id}` | Detalhar lote |
| 9 | PUT | `/lots/{id}` | Atualizar lote |
| 10 | DELETE | `/lots/{id}` | Remover lote |
| 11 | GET | `/lots/{id}/movements` | Listar movimentações do lote |
| 12 | POST | `/lots/{id}/movements` | Criar movimentação |
| 13 | GET | `/movements/{id}` | Detalhar movimentação |
| 14 | GET | `/dashboard` | Resumo geral (totais, alertas) |
| 15 | GET | `/reconciliation` | Conciliação de estoques |
| 16 | GET | `/autonomy-sources` | Fontes para Autonomia Alimentar |
| 17 | POST | `/lots/{id}/status` | Alterar status do lote |
| 18 | GET | `/losses` | Relatório de perdas |
| 19 | GET | `/export` | Exportar dados (CSV/JSON) |

### Request/Response examples

#### POST `/api/v1/feed-inventory/lots`

Request:
```json
{
  "facility_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Silagem 2026 - Talhão A",
  "type": "silagem",
  "quantity_kg": 50000,
  "dry_matter_pct": 35,
  "total_cost": 25000.00,
  "daily_consumption_kg": 800,
  "harvest_date": "2026-06-15",
  "notes": "Produção própria - milho híbrido"
}
```

Response (201):
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "facility_id": "550e8400-e29b-41d4-a716-446655440000",
  "farm_id": "770e8400-e29b-41d4-a716-446655440002",
  "name": "Silagem 2026 - Talhão A",
  "type": "silagem",
  "quantity_kg": 50000,
  "dry_matter_pct": 35,
  "contamination_pct": 0,
  "total_cost": 25000.00,
  "cost_per_kg": 0.50,
  "cost_per_kg_ms": 1.43,
  "daily_consumption_kg": 800,
  "days_remaining": 21.88,
  "estimated_end_date": "2026-08-04",
  "loss_pct": 0,
  "loss_value": 0,
  "status": "available",
  "harvest_date": "2026-06-15",
  "notes": "Produção própria - milho híbrido",
  "created_at": "2026-07-13T22:00:00Z",
  "updated_at": "2026-07-13T22:00:00Z"
}
```

#### POST `/api/v1/feed-inventory/lots/{id}/movements`

Request (withdrawal):
```json
{
  "type": "withdrawal",
  "quantity_kg": 1600,
  "reference_date": "2026-07-13",
  "notes": "Retirada para alimentação do rebanho"
}
```

Response (201):
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440003",
  "lot_id": "660e8400-e29b-41d4-a716-446655440001",
  "type": "withdrawal",
  "quantity_kg": -1600,
  "reference_date": "2026-07-13",
  "created_at": "2026-07-13T22:05:00Z",
  "immutable": true
}
```

#### GET `/api/v1/feed-inventory/dashboard`

Response (200):
```json
{
  "total_facilities": 3,
  "total_lots": 12,
  "total_quantity_kg": 185000,
  "total_cost": 92500.00,
  "total_ms_physical_kg": 64750,
  "total_ms_usable_kg": 63455,
  "lots_low_stock": 2,
  "lots_expired": 0,
  "alert_messages": [
    "Lote 'Silagem Bunker 3' com estoque abaixo de 20%",
    "Lote 'Feno Cocho 1' com data fim estimada < 7 dias"
  ]
}
```

## Códigos de erro

| Código | HTTP | Descrição |
|--------|------|-----------|
| `FACILITY_NOT_FOUND` | 404 | Instalação não encontrada |
| `LOT_NOT_FOUND` | 404 | Lote não encontrado |
| `MOVEMENT_NOT_FOUND` | 404 | Movimentação não encontrada |
| `INSUFFICIENT_STOCK` | 400 | Estoque insuficiente para retirada |
| `NEGATIVE_BALANCE` | 400 | Operação resultaria em saldo negativo |
| `INVALID_MOVEMENT_TYPE` | 400 | Tipo de movimentação inválido |
| `QUARANTINE_RESTRICTION` | 400 | Lote em quarentena não pode ser movimentado |
| `FACILITY_IN_USE` | 409 | Instalação possui lotes associados |
| `VALIDATION_ERROR` | 400 | Dados de entrada inválidos |
| `UNAUTHORIZED` | 401 | Não autenticado |
| `FORBIDDEN` | 403 | Sem permissão |

## Formato de paginação

```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "per_page": 20,
  "pages": 3
}
```

Query params: `page` (default 1), `per_page` (default 20, max 100), `sort` (default created_at), `order` (default desc).

## Formato de autonomy-sources

```json
{
  "sources": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "type": "feed_inventory",
      "name": "Silagem 2026 - Talhão A",
      "quantity_kg": 48400,
      "ms_usable_kg": 16740,
      "cost_per_kg_ms": 1.43,
      "days_remaining": 20.93,
      "facility_name": "Silo Principal"
    }
  ],
  "total_ms_usable_kg": 63455,
  "last_updated": "2026-07-13T22:00:00Z"
}
```
