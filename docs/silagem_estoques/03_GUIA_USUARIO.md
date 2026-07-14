# 03 — Guia do Usuário

## Visão Geral do Dashboard

O dashboard de Silagem e Estoques mostra um resumo consolidado de todos os estoques:

- **Total de instalações**: quantidade de instalações cadastradas e ativas
- **Total de lotes**: quantidade de lotes registrados
- **Estoque total (kg)**: soma de quantity_kg de todos os lotes
- **Custo total (R$)**: soma de total_cost de todos os lotes
- **MS Física Total (kg)**: soma de MS_physical de todos os lotes
- **MS Utilizável Total (kg)**: soma de MS_usable de todos os lotes
- **Alertas**: lotes com estoque baixo, data fim próxima, ou status irregular

### Alertas exibidos

- Lote com estoque abaixo de 20% da capacidade
- Lote com data fim estimada inferior a 7 dias
- Lote com status quarantined
- Lote com perda acumulada > 10%

## Criando Instalações de Armazenamento

1. Acesse **Estoques → Instalações**
2. Clique em **Nova Instalação**
3. Preencha:
   - **Nome**: nome identificador (ex: "Silo Principal", "Bunker do Talhão 3")
   - **Tipo**: silo, bunker, cocho, depósito, outro
   - **Capacidade (kg)**: capacidade máxima em quilogramas (opcional)
   - **Capacidade (m³)**: capacidade máxima em metros cúbicos (opcional)
   - **Localização**: descrição da localização física
4. Clique em **Salvar**

### Dicas

- Use nomes descritivos e padronizados
- Cadastre a capacidade real para gerar alertas de lotura
- O tipo ajuda na filtragem e organização

## Criando Lotes de Insumos

1. Acesse **Estoques → Lotes**
2. Clique em **Novo Lote**
3. Preencha:
   - **Nome**: identificação do lote (ex: "Silagem 2026 - Talhão A")
   - **Instalação**: selecione a instalação de armazenamento
   - **Tipo**: silagem, feno, concentrado, mistura, outro
   - **Quantidade (kg)**: quantidade inicial em kg
   - **Matéria Seca (%)**: percentual de matéria seca
   - **Custo Total (R$)**: custo total do lote
   - **Consumo Diário (kg)**: consumo estimado por dia
   - **Data de Colheita/Recebimento**: data de produção ou aquisição
   - **Observações**: informações adicionais
4. Clique em **Salvar**

### Cálculos automáticos ao criar

O sistema calcula automaticamente:
- **Custo por kg** = Custo Total / Quantidade
- **Custo por kg de MS** = Custo Total / MS Utilizável
- **Dias restantes** = MS Utilizável / Consumo Diário
- **Data fim estimada** = Hoje + Dias restantes

## Registrando Movimentações

### Entrada

Para registrar entrada de nova mercadoria:

1. Acesse o lote desejado
2. Clique em **Registrar Movimentação → Entrada**
3. Informe a **quantidade (kg)** e a **data de referência**
4. Adicione observações se necessário
5. Confirme

A entrada aumenta o saldo do lote.

### Retirada

Para registrar retirada para alimentação ou transferência:

1. Acesse o lote desejado
2. Clique em **Registrar Movimentação → Retirada**
3. Informe a **quantidade (kg)** e a **data de referência**
4. Adicione observações
5. Confirme

**Importante**: o sistema verifica se há estoque suficiente. Se a retirada ultrapassar o saldo, a operação será rejeitada.

### Perda

Para registrar perda de insumo:

1. Acesse o lote desejado
2. Clique em **Registrar Movimentação → Perda**
3. Informe:
   - **Quantidade perdida (kg)**
   - **Percentual de perda (%)**
   - **Motivo**: selecione o motivo (avaria, contaminação, mofo, umidade, pragas, estrutural, manuseio, outro)
   - **Data de referência**
   - **Observações**: descreva detalhes do ocorrido
4. Confirme

### Ajuste

Para corrigir erro de lançamento anterior:

1. Acesse o lote desejado
2. Clique em **Registrar Movimentação → Ajuste**
3. Selecione o tipo:
   - **Ajuste positivo**: aumenta o saldo (correção para cima)
   - **Ajuste negativo**: reduz o saldo (correção para baixo)
4. Informe a **quantidade (kg)**, a **data de referência** e o **motivo do ajuste**
5. Confirme

**Nota**: a movimentação original permanece no histórico. O ajuste é um novo registro.

## Visualizando Histórico

1. Acesse **Estoques → Lotes**
2. Clique em um lote
3. Aba **Movimentações**: lista cronológica de todas as movimentações
4. Cada movimentação mostra: tipo, quantidade, data, responsável, observações

### Filtros disponíveis

- Por tipo de movimentação
- Por período
- Por responsável

## Conciliação

A conciliação verifica a integridade dos dados entre estoque físico e registros.

1. Acesse **Estoques → Conciliação**
2. Selecione o período
3. O sistema exibe:
   - Saldo registrado vs. saldo físico informado
   - Diferenças encontradas
   - Lotes com divergências
4. Para resolver divergências, registre uma movimentação de ajuste

## Importando para Autonomia Alimentar

1. Acesse **Autonomia Alimentar → Fontes de Alimentação**
2. Clique em **Importar de Silagem e Estoques**
3. Selecione os lotes que deseja incluir como fonte
4. Ajuste os percentuais de contribuição conforme necessário
5. Confirme

**Importante**: a importação é somente leitura. O estoque NÃO é reduzido quando usado em simulações de Autonomia Alimentar.

## Alertas e Warnings

O sistema gera alertas automáticos:

| Alerta | Condição |
|--------|----------|
| Estoque baixo | Lote com quantity_kg < 20% da capacidade da instalação |
| Data fim próxima | days_remaining < 7 dias |
| Perda elevada | loss_pct > 10% |
| Quarentena | Lote com status quarantined |
| Estoque zero | Lote com quantity_kg = 0 e status diferente de depleted |

## Configuração da Feature Flag

Para ativar o módulo Silagem e Estoques, adicione ao `docker-compose.staging.yml`:

```yaml
environment:
  - ENABLE_FEED_INVENTORY=true
```

Ou no `.env`:

```
ENABLE_FEED_INVENTORY=true
```

Reinicie o container após a alteração.
