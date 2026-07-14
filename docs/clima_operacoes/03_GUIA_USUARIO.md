# Guia do Usuário

## Acessando o Módulo

1. Faça login no WiNS Hub Agro
2. No menu lateral, clique em **Clima e Operações** (quando a feature flag estiver ativa)

## Configuração Inicial

1. Acesse a página Clima e Operações
2. Selecione a fazenda
3. Cadastre as coordenadas (latitude e longitude)
4. Confirme o timezone
5. Clique em **Salvar configuração**

## Dashboard

O dashboard mostra:
- **Condição atual**: temperatura, sensação, umidade, chuva, vento, rajadas, nuvens
- **Previsão diária**: mínima, máxima, chuva, probabilidade, vento
- **Chuva recente**: acumulado em 7 dias com gráfico visual
- **Janelas operacionais**: classificação e fatores para cada tipo de operação

## Janelas Operacionais

Cada janela mostra:
- **Tipo**: Corte, Ensilagem, Fenação, Pastagem, Campo ou Calor
- **Score**: 0-100
- **Classificação**: Favorável, Atenção, Desfavorável ou Dados insuficientes
- **Fatores positivos**: o que favorece a operação
- **Riscos**: o que pode prejudicar a operação

## Atualização

Clique em **Atualizar** para forçar nova consulta ao provedor. O sistema respeita cooldown de 60 segundos.

## Integrações

### Pasto Vivo
Na página Pasto Vivo, o contexto climático mostra:
- Chuva acumulada recente
- Chuva prevista
- Temperatura atual
- Status de calor
- Aviso sobre uso de dados como contexto

### Colheita e Silos
Na página Colheita e Silos, para cada plano:
- Previsão durante o período planejado
- Precipitação esperada
- Probabilidade de chuva
- Fatores de risco

**Importante**: O clima não altera automaticamente datas, status ou lotes.
