# Autonomia Alimentar — Testes e Evidências

## Testes unitários

### Domínio (`test_fase1_food_autonomy_domain.py`)
- Demanda por categoria (7 testes)
- Pastagem utilizável (6 testes)
- Estoque utilizável (5 testes)
- Cálculo de autonomia (9 testes)
- Validação de entrada (5 testes)
- **Total: 32 testes**

### Serviço (`test_fase1_food_autonomy_service.py`)
- Simulação (2 testes)
- Criação de cenário (1 teste)
- Listagem (1 teste)
- Serialização decimal (1 teste)
- Validação de entrada (2 testes)
- Repository (3 testes)
- **Total: 10 testes**

### API (`test_fase1_food_autonomy_api.py`)
- Endpoints (3 testes)
- Headers (1 teste)
- Request ID (1 teste)
- Schemas (10 testes)
- Security (5 testes)
- **Total: 20 testes**

### Security (`test_fase1_food_autonomy_security.py`)
- Forbidden imports (5 testes)
- Security patterns (10 testes)
- PII (3 testes)
- **Total: 18 testes**

### Staging (`test_fase1_food_autonomy_staging.py`)
- Health (1 teste)
- Auth (2 testes)
- Simulação (2 testes)
- **Total: 5 testes (condicional)**

## Total de testes novos: 85

## Testes de integração HTTP

| # | Teste | Resultado |
|---|---|---|
| 1 | Rota sem auth redireciona | ✓ |
| 2 | Simulate sem auth retorna 401 | ✓ |
| 3 | List sem auth retorna 401 | ✓ |
| 4 | Login funciona | ✓ |
| 5 | Demanda = 225.00 | ✓ |
| 6 | Versão da fórmula | ✓ |
| 7 | Cache-Control: no-store | ✓ |
| 8 | Feature flag desligada | ✓ |
| 9 | Decimais como strings | ✓ |
| 10 | Sem IDs internos | ✓ |

## Testes de integração UI

| # | Teste | Resultado |
|---|---|---|
| 1 | Página retorna 200 | ✓ |
| 2 | Título presente | ✓ |
| 3 | Seletor de fazenda | ✓ |
| 4 | Formulário rebanho | ✓ |
| 5 | Formulário pasto | ✓ |
| 6 | Formulário estoque | ✓ |
| 7 | Botão calcular | ✓ |
| 8 | Histórico | ✓ |
| 9 | CSS carrega | ✓ |
| 10 | Alpine.js carrega | ✓ |
