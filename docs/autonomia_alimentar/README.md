# Autonomia Alimentar — Documentação

## Documentos

| # | Documento | Descrição |
|---|---|---|
| 01 | [Escopo MVP](01_ESCOPO_MVP.md) | Funcionalidades, limites e decisões de produto |
| 02 | [Fórmulas](02_FORMULAS.md) | Fórmulas com Decimal, exemplos e versão |
| 03 | [Modelo de Dados](03_MODELO_DADOS.md) | 4 tabelas no schema nutrition |
| 04 | [Contrato da API](04_CONTRATO_API.md) | Endpoints, entrada, saída, validações |
| 05 | [Guia do Usuário](05_GUIA_USUARIO.md) | Como usar, glossário e dicas |
| 06 | [Runbook Staging](06_RUNBOOK_STAGING.md) | Iniciar, testar e parar o staging |
| 07 | [Testes e Evidências](07_TESTES_E_EVIDENCIAS.md) | 84 testes, HTTP e UI |
| 08 | [Limitações e Próximos Passos](08_LIMITACOES_E_PROXIMOS_PASSOS.md) | O que falta e roadmap |

## Início rápido

```bash
# 1. Staging
bash scripts/fase0d/start_staging.sh
bash scripts/fase1_autonomia/apply_staging.sh

# 2. Ativar flag
# Adicione ENABLE_FOOD_AUTONOMY=true ao docker-compose.staging.yml

# 3. Testar
cd app && python3 -m unittest discover -s tests -p 'test_fase1_food_autonomy_*.py' -v
```

## Integração com Pasto Vivo

O módulo **Autonomia Alimentar** pode se integrar ao módulo **Pasto Vivo** para enriquecer os cálculos nutricionais com dados reais de pastagem.

### Como funciona

1. **Dados de entrada**: O Pasto Vivo fornece biomassa disponível por talhão
2. **Cálculo de autonomia**: O sistema estima dias de autonomia baseado no consumo do rebanho
3. **Recomendações**: Sugestões de manejo para manter a produção

### Configuração

Para ativar a integração:

```bash
# No docker-compose.staging.yml
environment:
  - ENABLE_PASTO_VIVO=true
  - ENABLE_FOOD_AUTONOMY=true
  - ENABLE_INTEGRATION_PASTO_VIVO_FOOD=true
```

### Uso

1. Cadastre talhões no módulo Pasto Vivo
2. Registre medições regularmente
3. No Autonomia Alimentar, os dados aparecerão automaticamente em **Fontes de Alimentação**
4. Ajuste os percentuais conforme necessário

### Documentação

Consulte a documentação completa em [`docs/pasto_vivo/`](../pasto_vivo/).

## Integração com Silagem e Estoques

O módulo **Autonomia Alimentar** também se integra ao módulo **Silagem e Estoques** para enriquecer os cálculos com dados reais de estoque de insumos armazenados.

### Como funciona

1. **Botão "Importar"**: na tela de Fontes de Alimentação, clique em "Importar de Silagem e Estoques"
2. **Seleção de lotes**: escolha quais lotes deseja incluir como fonte de alimentação
3. **Source type**: cada importação é registrada com tipo `feed_inventory` para rastreabilidade
4. **Dados importados**: quantidade, MS utilizável, custo por kg de MS, dias restantes

### Regras importantes

- A importação é **somente leitura** — o estoque NÃO é reduzido quando usado em simulações de Autonomia Alimentar
- Alterações no estoque (retiradas, perdas) são refletidas automaticamente na próxima consulta
- O usuário pode ajustar o percentual de contribuição de cada fonte importada

### Configuração

```bash
# No docker-compose.staging.yml
environment:
  - ENABLE_FOOD_AUTONOMY=true
  - ENABLE_FEED_INVENTORY=true
```

### Documentação

Consulte a documentação completa em [`docs/silagem_estoques/`](../silagem_estoques/).
