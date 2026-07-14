# Silagem e Estoques — Documentação

## Descrição

Módulo de gestão de estoques de silagem e outros insumos alimentares para o sistema WiNS Agro. Permite o cadastro de instalações de armazenamento, lotes, movimentações (entradas, retiradas, perdas, ajustes), controle de custos e conciliação, integrando-se ao módulo de Autonomia Alimentar como fonte de dados de alimentação.

## Feature Flag

| Flag | Descrição | Padrão |
|------|-----------|--------|
| `ENABLE_FEED_INVENTORY` | Ativa o módulo Silagem e Estoques | `false` |

## Documentos

| # | Documento | Descrição |
|---|---|---|
| 01 | [Escopo e Regras](01_ESCOPO_E_REGRAS.md) | Funcionalidades, limites, regras de negócio e fórmulas |
| 02 | [Modelo de Dados e API](02_MODELO_DADOS_E_API.md) | Schema, 3 tabelas, 19 endpoints |
| 03 | [Guia do Usuário](03_GUIA_USUARIO.md) | Dashboard, cadastros, movimentações e uso |
| 04 | [Staging, Testes e Limitações](04_STAGING_TESTES_E_LIMITACOES.md) | Ambiente de teste, testes e restrições |

## Início rápido

```bash
# 1. Staging
bash scripts/feed_inventory/start_staging.sh

# 2. Ativar flag
# Adicione ENABLE_FEED_INVENTORY=true ao docker-compose.staging.yml

# 3. Aplicar migrations
python scripts/feed_inventory/apply_migrations.py

# 4. Testar
cd app && python3 -m unittest discover -s tests -p 'test_feed_inventory_*.py' -v
```

## Integrações

### Autonomia Alimentar

O módulo fornece dados de estoque alimentar para o cálculo de autonomia. O botão "Importar" no Autonomia Alimentar permite carregar estoques do feed_inventory como fonte do tipo `feed_inventory`. A importação é somente leitura — o estoque NÃO é reduzido por simulações.

### Pasto Vivo

Módulo irmão. Enquanto Pasto Vivo gerencia pastagens vivas (biomassa, lotação, descanso), Silagem e Estoques gerencia insumos armazenados (silagem, feno, concentrados). Ambos alimentam a Autonomia Alimentar com fontes complementares.

### Colheita e Silos

Planos concluídos criam lotes reais e movimentos `initial_balance` neste módulo. Cada lote recebe origem “Colheita e Silos”, referência ao UUID do plano e vínculo persistente pela alocação. Depois da criação, o lote segue independente no ledger de estoque; o plano concluído permanece imutável.

## Fórmulas (feed_inventory.v1)

```
MS_physical   = quantity_kg × (dry_matter_pct / 100)
MS_usable     = MS_physical × (1 - contamination_pct / 100)
cost_per_kg   = total_cost / quantity_kg
cost_per_kg_ms = total_cost / MS_usable
loss_value    = quantity_kg × cost_per_kg × (loss_pct / 100)
days_remaining = MS_usable / daily_consumption_kg
estimated_end_date = today + days_remaining
```

## Status

- **MVP** — Implementação funcional mínima com 3 tabelas, 19 endpoints e documentação completa.
- Movimentações imutáveis; correções apenas via novo lançamento de ajuste.
- Saldo nunca negativo (regra de negócio).
