# Autonomia Alimentar — Escopo MVP

## Objetivo

Permitir que o produtor calcule, salve e compare cenários de autonomia alimentar respondendo:
"por quantos dias o alimento disponível sustenta o rebanho?"

## Funcionalidades

### Rebanho
- Cadastro por categoria (vacas lactação, secas, novilhas, garrotes, bezerros, touros, outros)
- Quantidade de animais, peso médio, consumo % do peso vivo
- Cálculo automático de demanda diária por categoria e total

### Pastagem
- Cadastro por área (identificação, hectares, kg MS/ha, utilização)
- Cálculo de matéria seca utilizável

### Estoques
- Cadastro por tipo (silagem, feno, pré-secado, concentrado, suplementos, subprodutos)
- Quantidade, % matéria seca, % aproveitamento
- Cálculo de matéria seca utilizável

### Planejamento
- Nome, data de referência, meta de autonomia, margem de segurança
- Observações

### Resultado
- Demanda diária total
- MS disponível (pastagens + estoques)
- Autonomia em dias
- Saldo vs meta (dias e kg MS)
- Status: Crítico, Atenção, Adequado, Incompleto
- Data estimada de término
- Composição percentual do estoque

### Persistência
- Cenários salvos com todos os itens
- Histórico por fazenda
- Arquivamento lógico

## Fórmulas

Todas as fórmulas usam `Decimal` — nenhum `float` é usado no cálculo.

## Segurança

- Autenticação JWT obrigatória
- Autorização por organização e fazenda
- IDOR bloqueado (cross-tenant retorna 404)
- Viewer não altera cenários
- Feature flag `ENABLE_FOOD_AUTONOMY` (default false)
