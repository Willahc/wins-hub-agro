# 01 — Escopo e Regras de Negócio

## O que o módulo cobre

O módulo Silagem e Estoques gerencia o ciclo de vida de insumos alimentares armazenados:

- **Instalações de armazenamento** (silos, bunkers, cochos, depósitos): cadastro, capacidade, localização
- **Lotes de insumos**: identificação, tipo, quantity_kg, dry_matter_pct, custo total, status
- **Movimentações**: entradas, retiradas, perdas, ajustes positivos, ajustes negativos, saldo inicial
- **Controle de perdas**: motivo, percentual, valor monetário
- **Controle de custos**: custo por kg, custo por kg de MS, custo por kg de MS utilizável
- **Conciliação**: verificação de integridade entre estoque físico e registros
- **Previsão**: dias restantes estimados, data fim estimada

## O que NÃO cobre

- Ração industrial ou processamento industrial
- Formulação nutricional ou balanceamento de dietas
- Sensores, IoT ou medição automática de umidade/temperatura
- Rastreabilidade de qualidade (micotoxinas, fermentação)
- Contratos de compra/venda de insumos
- Gestão de fornecedores ou logística de transporte
- Integrção com balanças ou sistemas de pesagem
- Conciliação automática com notas fiscais

## Regras de negócio

### R1: Saldo nunca negativo

O saldo físico de qualquer lote em qualquer momento nunca pode ser negativo. Se uma movimentação de retirada ultrapassar o saldo disponível, o sistema deve rejeitar a operação com erro `INSUFFICIENT_STOCK`.

### R2: Movimentações imutáveis

Uma vez criada, uma movimentação não pode ser editada nem excluída. Qualquer correção deve ser feita via nova movimentação de ajuste (ajustepositivo ou ajuste_negativo).

### R3: Correções via novo lançamento

Erros de lançamento são corrigidos criando-se uma nova movimentação do tipo `adjustment_positive` ou `adjustment_negative`, com campo `reason` descrevendo o motivo da correção. A movimentação original permanece no histórico.

### R4: Sem perda automática

O sistema NÃO registra perdas automaticamente. Toda perda deve ser registrada explicitamente como uma movimentação do tipo `loss` com motivo e percentual informados pelo usuário.

### R5: Frontend não é fonte de verdade

Valores exibidos no frontend (saldo, custo, MS) são derivados e NUNCA devem ser usados como fonte de verdade para decisões. A fonte de verdade é sempre o banco de dados via API.

### R6: Conciliação manual

A conciliação é um processo de verificação, não de correção automática. Diferenças identificadas devem ser resolvidas pelo usuário com lançamentos de ajuste.

## Fórmulas

### MS Físico (Massa Seca Física)

```
MS_physical = quantity_kg × (dry_matter_pct / 100)
```

### MS Utilizável

```
MS_usable = MS_physical × (1 - contamination_pct / 100)
```

### Custo por kg

```
cost_per_kg = total_cost / quantity_kg
```

### Custo por kg de MS

```
cost_per_kg_ms = total_cost / MS_usable
```

### Valor da Perda

```
loss_value = quantity_kg × cost_per_kg × (loss_pct / 100)
```

### Dias Restantes

```
days_remaining = MS_usable / daily_consumption_kg
```

### Data Fim Estimada

```
estimated_end_date = today + days_remaining
```

## Definições de Status

| Status | Descrição |
|--------|-----------|
| `available` | Lote disponível para uso. Pode ser retirado ou transferido. |
| `reserved` | Lote reservado para uso específico. Ainda físico, mas comprometido. |
| `opened` | Lote aberto em campo ou cocho. Em uso ativo. |
| `depleted` | Lote esgotado. Saldo zero. Mantido para histórico. |
| `quarantined` | Lote em quarentena. Não pode ser movimentado até liberação. |
| `archived` | Lote arquivado. Fora de uso, mantido apenas para consulta. |

## Tipos de movimentação

| Tipo | Descrição |
|------|-----------|
| `initial_balance` | Saldo inicial ao cadastrar lote existente. Cria o primeiro registro. |
| `entry` | Entrada de nova mercadoria no lote (compra, produção própria, transferência). |
| `withdrawal` | Retirada de mercadoria do lote (alimentação, venda, transferência). |
| `loss` | Registro de perda (quebra, avaria, contaminação, mofa, etc.). |
| `adjustment_positive` | Ajuste positivo para correção de erro de lançamento anterior. |
| `adjustment_negative` | Ajuste negativo para correção de erro de lançamento anterior. |

## Motivos de perda

| Código | Descrição |
|--------|-----------|
| `spoil` | Avaria ou deterioração do insumo |
| `contamination` | Contaminação por micotoxinas, bactérias ou corpos estranhos |
| `mold` | Desenvolvimento de mofo |
| `moisture` | Excesso de umidade causando perda |
| `pest` | Ataque de pragas (insetos, roedores) |
| `structural` | Vazamento ou dano na instalação de armazenamento |
| `handling` | Erro de manuseio ou operação |
| `other` | Outro motivo (descrever no campo `reason`) |
