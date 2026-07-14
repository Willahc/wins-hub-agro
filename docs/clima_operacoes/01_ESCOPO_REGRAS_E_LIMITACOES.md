# Escopo, Regras e Limitações

## Escopo do Módulo

O módulo Clima e Janelas Operacionais fornece:

1. **Condição meteorológica atual** da fazenda
2. **Previsão diária** para os próximos dias
3. **Previsão horária** para janelas operacionais
4. **Chuva acumulada recente** (7 dias)
5. **Janelas operacionais** para corte, ensilagem, fenação, pastagem, campo e calor
6. **Dashboard** com síntese de todas as informações
7. **Integração** com Pasto Vivo e Colheita e Silos

## Regras

### Feature Flag
- `ENABLE_WEATHER_OPERATIONS` controla disponibilidade
- Default: `false`
- Staging: `true`
- Produção: `false` ou ausente

### Autenticação
- Leitura: `FARM_READ`
- Escrita (perfil, refresh, avaliação): `FARM_OPERATE`
- Viewer: somente consulta

### Cache
- Condição atual: 20 minutos
- Previsão horária: 45 minutos
- Previsão diária: 120 minutos
- Histórico: 720 minutos
- Fallback: até 12 horas

### Cooldown
- Refresh respeita cooldown de 60 segundos por fazenda
- Retorna 403 (ForbiddenError) quando violado

### Janelas Operacionais
- Score de 0 a 100
- Classificações: Favorável (≥75), Atenção (45-74), Desfavorável (<45), Dados insuficientes
- Fatores positivos e de risco são explicáveis
- Regra versionada: `operational_windows.v1`

## Limitações

- Não substitui estação meteorológica
- Não faz previsão própria
- Não usa machine learning
- Não controla irrigação
- Não altera automaticamente dados operacionais
- Não emite recomendações definitivas
