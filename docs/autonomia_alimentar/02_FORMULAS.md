# Autonomia Alimentar — Fórmulas

## 7.1 Demanda por categoria

```
peso_total_kg = quantidade_animais × peso_medio_kg
demanda_ms_categoria_kg_dia = peso_total_kg × (consumo_ms_percentual / 100)
```

Exemplo: 20 × 450 × 2.5% = 225 kg MS/dia

## 7.2 Matéria seca utilizável da pastagem

```
ms_pasto_utilizavel_kg = area_ha × ms_disponivel_kg_ha × (percentual_utilizacao / 100)
```

Exemplo: 10 ha × 2.000 kg/ha × 50% = 10.000 kg MS

## 7.3 Matéria seca utilizável de alimento armazenado

```
ms_estoque_utilizavel_kg = quantidade_materia_natural_kg × (percentual_materia_seca / 100) × (percentual_aproveitamento / 100)
```

Exemplo: 10.000 kg × 35% × 90% = 3.150 kg MS

## 7.4 Total disponível

```
ms_total_utilizavel_kg = ms_pasto_total + ms_estoques_total
```

## 7.5 Autonomia

```
Se demanda > 0:
  autonomia_dias = ms_total_utilizavel_kg / demanda_ms_total_kg_dia
Senão:
  retornar resultado incompleto
```

## 7.6 Meta

```
ms_necessaria_para_meta = demanda_ms_total_kg_dia × meta_dias
saldo_ms = ms_total_utilizavel_kg - ms_necessaria_para_meta
saldo_dias = autonomia_dias - meta_dias
```

## 7.7 Percentual de segurança

```
ms_reserva_seguranca = ms_total_utilizavel_kg × (percentual_seguranca / 100)
ms_disponivel_planejamento = ms_total_utilizavel_kg - ms_reserva_seguranca
```

A autonomia usa o total após a reserva.

## 7.8 Data estimada de término

```
data_termino_estimada = data_referencia + floor(autonomia_dias)
```

## Versão

Todas as fórmulas são registradas com versão `food_autonomy.v1`.
