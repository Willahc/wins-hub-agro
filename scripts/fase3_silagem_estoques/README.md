# Fase 3 — Silagem e Estoques

Migrações do módulo de gestão de silagem e estoques de alimentação.

## Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `001_storage_schema.sql` | Cria schema `storage` e tabelas: `feed_storage_facilities`, `feed_lots`, `feed_stock_movements` |
| `002_storage_grants.sql` | Grants de acesso para roles `wins_agro_app`, `wins_agro_readonly`, `wins_agro_migrator` |
| `090_storage_seed_staging.sql` | Dados sintéticos para validação no staging (2 facilities, 4 lots, 5+ movimentações) |
| `099_storage_down.sql` | Rollback completo — dropa tabelas e schema na ordem inversa |
| `apply_staging.sh` | Script para aplicar todas as migrações no staging via Docker |
| `test_http.sh` | Testes HTTP de integração (24 testes: CRUD, movimentações, validações) |
| `test_ui.sh` | Testes de UI (4 testes: página, auth, assets, menu) |

## Execução

### Aplicar migrações no staging

```bash
bash scripts/fase3_silagem_estoques/apply_staging.sh
```

### Rodar testes HTTP

```bash
bash scripts/fase3_silagem_estoques/test_http.sh
```

### Rodar testes de UI

```bash
bash scripts/fase3_silagem_estoques/test_ui.sh
```

### Rollback

```bash
docker exec -i wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging \
  -v ON_ERROR_STOP=1 \
  -f - < scripts/fase3_silagem_estoques/099_storage_down.sql
```

## Estrutura do Schema

### feed_storage_facilities
Estruturas de armazenamento (silos, galpões, depósitos).

### feed_lots
Lotes de alimento vinculados a uma facility. Controle de quantidade, MS, utilization, custo e status.

### feed_stock_movements
Ledger imutável de movimentações. Tipos: `initial_balance`, `entry`, `withdrawal`, `loss`, `adjustment_positive`, `adjustment_negative`. Idempotência via `request_id` único por lote.

## Dados Sintéticos (Staging)

- **Farm**: Alfa (farm_id=1)
- **Facilities**: Silo Trincheira (100.000 kg), Galpão de Feno (20.000 kg)
- **Lots**: Silagem milho (60.000 kg), Feno (8.000 kg), Silagem antiga (2.500 kg restantes), Silagem em quarentena (15.000 kg)
- **Usuário**: mari@winshubagro.cloud
