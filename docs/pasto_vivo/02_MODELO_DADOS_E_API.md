# 02 — Modelo de Dados e API do Pasto Vivo

## Schema

O módulo Pasto Vivo utiliza o schema `pasture` no PostgreSQL.

## Tabelas

### 1. pasture.paddocks

Tabela principal de talhões de pastagem.

```sql
CREATE TABLE pasture.paddocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_id UUID NOT NULL REFERENCES fazenda.cliente(id),
    name VARCHAR(100) NOT NULL,
    area_ha DECIMAL(10,4) NOT NULL CHECK (area_ha > 0),
    forage_type VARCHAR(50) NOT NULL,
    conversion_factor DECIMAL(5,2) NOT NULL DEFAULT 120.0,
    rest_height_cm DECIMAL(5,2) NOT NULL DEFAULT 10.0,
    growth_rate_cm_day DECIMAL(5,3) NOT NULL DEFAULT 1.5,
    state VARCHAR(20) NOT NULL DEFAULT 'DISPONÍVEL',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id),
    updated_by UUID REFERENCES auth.users(id)
);

-- Índices
CREATE INDEX idx_paddocks_farm_id ON pasture.paddocks(farm_id);
CREATE INDEX idx_paddocks_state ON pasture.paddocks(state);
CREATE INDEX idx_paddocks_forage_type ON pasture.paddocks(forage_type);
```

**Colunas:**

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID | Identificador único (auto-gerado) |
| `farm_id` | UUID | Referência à fazenda |
| `name` | VARCHAR(100) | Nome do talhão |
| `area_ha` | DECIMAL(10,4) | Área em hectares |
| `forage_type` | VARCHAR(50) | Tipo de forrageira (ex: Brachiaria, Panicum) |
| `conversion_factor` | DECIMAL(5,2) | Fator de conversão para MST |
| `rest_height_cm` | DECIMAL(5,2) | Altura mínima de descanso |
| `growth_rate_cm_day` | DECIMAL(5,3) | Taxa de crescimento diário |
| `state` | VARCHAR(20) | Estado atual (DISPONÍVEL, EM_PASTEJO, EM_DESCANSO) |
| `created_at` | TIMESTAMP | Data de criação |
| `updated_at` | TIMESTAMP | Data de atualização |
| `created_by` | UUID | Usuário que criou |
| `updated_by` | UUID | UUID do usuário que atualizou por último |

### 2. pasture.measurements

Registros de medições de pastagem.

```sql
CREATE TABLE pasture.measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paddock_id UUID NOT NULL REFERENCES pasture.paddocks(id) ON DELETE CASCADE,
    measurement_date DATE NOT NULL DEFAULT CURRENT_DATE,
    height_cm DECIMAL(5,2) NOT NULL CHECK (height_cm >= 0),
    coverage_percent DECIMAL(5,2) NOT NULL CHECK (coverage_percent BETWEEN 0 AND 100),
    estimated_biomass_kg_ha DECIMAL(10,2),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

-- Índices
CREATE INDEX idx_measurements_paddock_id ON pasture.measurements(paddock_id);
CREATE INDEX idx_measurements_date ON pasture.measurements(measurement_date);
```

**Colunas:**

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID | Identificador único |
| `paddock_id` | UUID | Referência ao talhão |
| `measurement_date` | DATE | Data da medição |
| `height_cm` | DECIMAL(5,2) | Altura do pasto em cm |
| `coverage_percent` | DECIMAL(5,2) | Cobertura do solo (0-100%) |
| `estimated_biomass_kg_ha` | DECIMAL(10,2) | Biomassa estimada (kg/ha) |
| `notes` | TEXT | Observações |
| `created_at` | TIMESTAMP | Data de criação |
| `created_by` | UUID | Usuário que registrou |

### 3. pasture.grazing_records

Registros de pastejo e lotação.

```sql
CREATE TABLE pasture.grazing_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paddock_id UUID NOT NULL REFERENCES pasture.paddocks(id) ON DELETE CASCADE,
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE,
    animal_count INTEGER NOT NULL CHECK (animal_count > 0),
    animal_type VARCHAR(50) NOT NULL,
    average_weight_kg DECIMAL(7,2) NOT NULL,
    stocking_rate_ui_ha DECIMAL(8,4) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

-- Índices
CREATE INDEX idx_grazing_paddock_id ON pasture.grazing_records(paddock_id);
CREATE INDEX idx_grazing_dates ON pasture.grazing_records(start_date, end_date);
```

**Colunas:**

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID | Identificador único |
| `paddock_id` | UUID | Referência ao talhão |
| `start_date` | TIMESTAMP | Data/hora de início |
| `end_date` | TIMESTAMP | Data/hora de término (NULL = em andamento) |
| `animal_count` | INTEGER | Número de animais |
| `animal_type` | VARCHAR(50) | Tipo de animal (ex: Bovino, Ovino) |
| `average_weight_kg` | DECIMAL(7,2) | Peso médio em kg |
| `stocking_rate_ui_ha` | DECIMAL(8,4) | Densidade em UI/ha |
| `notes` | TEXT | Observações |
| `created_at` | TIMESTAMP | Data de criação |
| `created_by` | UUID | Usuário que registrou |

## API REST

Base URL: `/api/v1/pasto-vivo`

### Endpoints de Talhões

#### Listar talhões

```http
GET /api/v1/pasto-vivo/paddocks
```

**Query Parameters:**
- `farm_id` (UUID): Filtro por fazenda
- `state` (string): Filtro por estado
- `forage_type` (string): Filtro por tipo de forrageira
- `page` (int): Página (padrão: 1)
- `limit` (int): Itens por página (padrão: 20)

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "farm_id": "uuid",
      "name": "Talhão 1",
      "area_ha": 10.5,
      "forage_type": "Brachiaria",
      "state": "DISPONÍVEL",
      "latest_measurement": {
        "date": "2026-07-10",
        "height_cm": 25.0,
        "coverage_percent": 80.0,
        "estimated_biomass_kg_ha": 2400.0
      }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 5,
    "pages": 1
  }
}
```

#### Criar talhão

```http
POST /api/v1/pasto-vivo/paddocks
```

**Request Body:**
```json
{
  "farm_id": "uuid",
  "name": "Talhão 2",
  "area_ha": 15.0,
  "forage_type": "Panicum",
  "conversion_factor": 100.0,
  "rest_height_cm": 12.0,
  "growth_rate_cm_day": 1.2
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Talhão 2",
  "state": "DISPONÍVEL",
  "created_at": "2026-07-13T10:00:00Z"
}
```

#### Obter talhão

```http
GET /api/v1/pasto-vivo/paddocks/{id}
```

#### Atualizar talhão

```http
PUT /api/v1/pasto-vivo/paddocks/{id}
```

#### Excluir talhão

```http
DELETE /api/v1/pasto-vivo/paddocks/{id}
```

### Endpoints de Medições

#### Listar medições

```http
GET /api/v1/pasto-vivo/paddocks/{paddock_id}/measurements
```

#### Registrar medição

```http
POST /api/v1/pasto-vivo/paddocks/{paddock_id}/measurements
```

**Request Body:**
```json
{
  "measurement_date": "2026-07-13",
  "height_cm": 28.5,
  "coverage_percent": 85.0,
  "notes": "Após chuva de ontem"
}
```

### Endpoints de Pastejo

#### Iniciar pastejo

```http
POST /api/v1/pasto-vivo/paddocks/{paddock_id}/grazing/start
```

**Request Body:**
```json
{
  "animal_count": 50,
  "animal_type": "Bovino",
  "average_weight_kg": 450.0,
  "notes": "Lote de novilhos"
}
```

#### Encerrar pastejo

```http
POST /api/v1/pasto-vivo/paddocks/{paddock_id}/grazing/stop
```

#### Listar registros de pastejo

```http
GET /api/v1/pasto-vivo/paddocks/{paddock_id}/grazing
```

### Endpoints de Dashboard

#### Resumo geral

```http
GET /api/v1/pasto-vivo/dashboard/summary
```

**Response:**
```json
{
  "total_paddocks": 10,
  "available": 5,
  "grazing": 3,
  "resting": 2,
  "total_area_ha": 150.0,
  "average_coverage_percent": 75.0,
  "alerts": [
    {
      "paddock_id": "uuid",
      "paddock_name": "Talhão 3",
      "alert_type": "MEASUREMENT_EXPIRED",
      "message": "Medição com mais de 7 dias"
    }
  ]
}
```

### Endpoints de Integração

#### Exportar para Autonomia Alimentar

```http
GET /api/v1/pasto-vivo/integration/food-autonomy
```

**Query Parameters:**
- `farm_id` (UUID): Fazenda
- `date` (date): Data de referência

**Response:**
```json
{
  "farm_id": "uuid",
  "reference_date": "2026-07-13",
  "paddocks": [
    {
      "id": "uuid",
      "name": "Talhão 1",
      "area_ha": 10.5,
      "available_biomass_kg_ha": 2400.0,
      "days_of_autonomy": 15.2
    }
  ],
  "total_available_biomass_kg": 25200.0
}
```

## Integração com Autonomia Alimentar

O módulo Pasto Vivo se integra ao módulo de Autonomia Alimentar através de:

1. **Exportação de dados**: Endpoint `/integration/food-autonomy` fornece biomassa disponível
2. **Cálculo de autonomia**: Dias de autonomia baseados no consumo do rebanho
3. **Recomendações**: Quando repor ou rotacionar pastagens