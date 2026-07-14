# backfill_agro_real_001

## Diagnóstico

| Origem | Quantidade | Fazenda/cliente | Pode migrar? | Destino |
|--------|------------|-----------------|--------------|---------|
| foundation.operational_farms | 1 | Fazenda Demonstração | — | já é a fazenda ativa |
| foundation.organizations | 1 | Organização Demonstração | — | org ativa |
| pasture.* | 0 | — | não | — |
| storage.* | 0 | — | não | — |
| harvest.* | 0 | — | não | — |
| nutrition.* | 0 | — | não | — |
| climate.* | 0 | — | não | — |
| fazenda.cliente | 1 | id=17 Demonstração TO/Porto Nacional | parcial (UF) | foundation.operational_farms.state |
| fazenda.animal | 8 | cliente 17 | **não** (sem categoria/consumo/MS) | não inventar herd items |
| fazenda.medicao | 5 | pesos | **não** → pasto/estoque | domínio diferente |
| fazenda.movimentacao | 3 | entradas | **não** | sem lote agro |
| fazenda.estacao_monta | 2 | repro | **não** | fora do escopo agro |
| fazenda.cruzamento | 2 | repro | **não** | fora do escopo |
| fazenda.venda | 1 | comercial | **não** | fora do escopo |

## Classificação da fazenda

**B + D**: cadastro demonstrativo para liberar acesso multi-tenant; sem dados operacionais agro reais.

## Uso

```bash
# Dry-run (padrão)
docker exec -i wins_agro_v1-db-1 psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "SET app.dry_run = '1';" \
  -f - < scripts/producao/backfill_agro_real_001.sql

# Aplicar (só preenche state=TO se NULL)
docker exec -i wins_agro_v1-db-1 psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "SET app.dry_run = '0';" \
  -f - < scripts/producao/backfill_agro_real_001.sql
```

Rollback lógico do único campo:

```sql
UPDATE foundation.operational_farms
   SET state = NULL, updated_at = now()
 WHERE public_id = 'b0000000-0000-4000-8000-00000000000b'
   AND state = 'TO';
```
