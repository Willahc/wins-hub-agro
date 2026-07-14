# Escopo, cálculos e regras

Um plano possui uma ou mais áreas e zero ou mais alocações previstas. Produtividade é sempre informada pelo usuário.

```text
produção_bruta_kg = área_ha × produtividade_t_ha × 1.000
após_campo_kg = produção_bruta_kg × (1 - perda_campo_pct/100)
produção_líquida_kg = após_campo_kg × (1 - perda_ensilagem_pct/100)
matéria_seca_kg = produção_líquida_kg × matéria_seca_pct/100
ocupação_projetada_kg = estoque_atual_kg + alocação_kg
ocupação_pct = ocupação_projetada_kg / capacidade_kg × 100
```

Menos de 85% é `available`; de 85% a 100% é `near_capacity`; acima de 100% é `over_capacity`; capacidade nula é `unknown_capacity`. A conclusão recalcula capacidade com o estoque corrente e bloqueia excesso.

Planos concluídos são imutáveis e não podem ser arquivados silenciosamente. A conclusão exige soma dos lotes igual ao total real, é transacional e idempotente por `request_id` + hash do payload. Replay divergente retorna conflito.
