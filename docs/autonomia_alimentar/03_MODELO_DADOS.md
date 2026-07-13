# Autonomia Alimentar — Modelo de Dados

## Schema

`nutrition`

## Tabelas

### nutrition.food_autonomy_scenarios

| Campo | Tipo | Descrição |
|---|---|---|
| id | bigint PK | ID sequencial interno |
| public_id | uuid UNIQUE | ID público |
| organization_id | bigint FK | Organização |
| farm_id | bigint FK | Fazenda |
| name | text | Nome do cenário |
| reference_date | date | Data de referência |
| target_days | integer | Meta de autonomia (dias) |
| safety_margin_pct | numeric(5,2) | Margem de segurança |
| total_daily_demand_dm_kg | numeric(12,2) | Demanda diária total |
| total_pasture_dm_kg | numeric(12,2) | MS total de pastagens |
| total_stored_feed_dm_kg | numeric(12,2) | MS total de estoques |
| total_physical_dm_kg | numeric(12,2) | MS físico total |
| reserve_dm_kg | numeric(12,2) | Reserva de segurança |
| planning_available_dm_kg | numeric(12,2) | MS disponível para planejamento |
| autonomy_days | numeric(8,2) | Autonomia estimada |
| target_required_dm_kg | numeric(12,2) | MS necessário para meta |
| balance_dm_kg | numeric(12,2) | Saldo em kg MS |
| balance_days | numeric(8,2) | Saldo em dias |
| status | text | critical/warning/adequate/incomplete |
| estimated_end_date | date | Data estimada de término |
| formula_version | text | Versão da fórmula |
| notes | text | Observações |
| created_by_user_id | bigint | Usuário criador |
| created_at | timestamptz | Data de criação |
| updated_at | timestamptz | Data de atualização |
| archived_at | timestamptz | Data de arquivamento |

### nutrition.food_autonomy_herd_items

| Campo | Tipo | Descrição |
|---|---|---|
| id | bigint PK | ID sequencial |
| scenario_id | bigint FK | Cenário |
| category | text | Categoria |
| custom_category_name | text | Nome customizado |
| head_count | integer | Quantidade |
| average_weight_kg | numeric(8,2) | Peso médio |
| intake_pct_body_weight | numeric(5,2) | Consumo % PV |
| calculated_daily_demand_dm_kg | numeric(12,2) | Demanda calculada |
| display_order | integer | Ordem de exibição |

### nutrition.food_autonomy_pasture_items

| Campo | Tipo | Descrição |
|---|---|---|
| id | bigint PK | ID sequencial |
| scenario_id | bigint FK | Cenário |
| name | text | Identificação |
| area_ha | numeric(10,4) | Área em hectares |
| available_dm_kg_ha | numeric(10,2) | MS disponível por ha |
| utilization_pct | numeric(5,2) | Percentual de utilização |
| calculated_usable_dm_kg | numeric(12,2) | MS utilizável calculada |
| notes | text | Observação |
| display_order | integer | Ordem |

### nutrition.food_autonomy_feed_items

| Campo | Tipo | Descrição |
|---|---|---|
| id | bigint PK | ID sequencial |
| scenario_id | bigint FK | Cenário |
| feed_type | text | Tipo do alimento |
| name | text | Identificação |
| quantity_natural_kg | numeric(12,2) | Quantidade em matéria natural |
| dry_matter_pct | numeric(5,2) | % Matéria seca |
| utilization_pct | numeric(5,2) | % Aproveitamento |
| calculated_usable_dm_kg | numeric(12,2) | MS utilizável calculada |
| notes | text | Observação |
| display_order | integer | Ordem |

## Constraints

- `numeric` para todos os valores decimais
- `CHECK` constraints para percentuais (0–100) e quantidades (≥ 0)
- `UNIQUE` em public_id
- `FOREIGN KEY` com cascade delete nos itens
- Índices para farm_id, organization_id, reference_date e status
