# 01 — Escopo e Regras do Pasto Vivo

## O que o módulo faz

O Pasto Vivo é um módulo de gestão de pastagens vivas que permite:

- **Cadastro de talhões**: Registro de áreas de pastagem com dimensões, tipo de forrageira e histórico
- **Registro de medições**: Coleta de dados de altura, cobertura e estimates de biomassa
- **Controle de lotação**: Gestão de cargas animais por talhão e período
- **Previsão de descanso**: Cálculo de tempo mínimo de descanso entre pastejos
- **Dashboard**: Visão geral do estado das pastagens
- **Integração**: Dados para o módulo de Autonomia Alimentar

## O que NÃO faz (fora do escopo)

De acordo com a especificação, o módulo NÃO implementa:

- **Sensoriamento remoto**: Sem imagens de satélite, NDVI, drones ou GIS
- **Sensores IoT**: Sem coleta automática de dados via dispositivos
- **Inteligência artificial**: Sem modelos preditivos ou recomendações baseadas em IA
- **Análise espacial**: Sem mapas de qualidade de pastagem
- **Previsão do tempo**: Sem integração com dados meteorológicos
- **Gestão financeira**: Sem custos de produção ou análise econômica
- **Controle de pragas/doenças**: Sem monitoramento fitossanitário

## Estados do Talhão

O talhão pode estar em um dos seguintes estados:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  DISPONÍVEL │───▶│ EM_PASTEJO  │───▶│ EM_DESCANSO │
└─────────────┘    └─────────────┘    └─────────────┘
       ▲                                     │
       └─────────────────────────────────────┘
```

### Transições de estado

| De | Para | Condição |
|----|------|----------|
| DISPONÍVEL | EM_PASTEJO | Início do pastejo (inserção de carga animal) |
| EM_PASTEJO | EM_DESCANSO | Remoção de todos os animais ou atingimento do ponto de corte |
| EM_DESCANSO | DISPONÍVEL | Tempo mínimo de descanso atingido |
| EM_PASTEJO | DISPONÍVEL | Remoção antecipada (decisão manual) |
| EM_DESCANSO | EM_PASTEJO | Reintrodução de animais antes do descanso completo (com aviso) |

## Regras de Medição

### Frescor dos dados

| Dado | Validade máxima | Ação se expirado |
|------|----------------|------------------|
| Altura do pasto | 7 dias | Medição obrigatória antes de decisões |
| Cobertura do solo | 14 dias | Medição recomendada |
| Biomassa estimada | 7 dias | Recalcular com nova medição |
| Lotação atual | 24 horas | Atualização obrigatória |

### Frequência mínima de medições

- **Medição completa**: a cada 7 dias (recomendado)
- **Medição rápida**: a cada 3 dias (altura apenas)
- **Medição extraordinária**: sempre que houver mudança significativa (seca, chuva intensa)

## Fórmulas de Cálculo

### 1. Matéria Seca Total (MST)

```
MST (kg/ha) = Altura (cm) × Fator de Conversão × Cobertura (%)
```

Onde:
- **Fator de Conversão**: depende da forrageira (ex: 120 para Brachiaria, 100 para Panicum)
- **Cobertura**: fração decimal (0.0 a 1.0)

### 2. Matéria Seca Utilizável (MSU)

```
MSU (kg/ha) = MST × Taxa de Utilização
```

Onde:
- **Taxa de Utilização**: 40% para pastejo rotacionado (padrão)

### 3. Data Próximo Corte

```
Dias de Descanso = (Altura Atual - Altura de Corte) / Taxa de Crescimento
Próximo Corte = Data Atual + Dias de Descanso
```

Onde:
- **Altura de Corte**: altura mínima para remoção (ex: 10 cm)
- **Taxa de Crescimento**: cm/dia (varia com estação e solo)

## Versão

**pasture_live.v1** — Versão inicial do módulo

## Eventos de Auditoria

| Evento | Descrição |
|--------|-----------|
| `pasture.paddock.created` | Novo talhão cadastrado |
| `pasture.paddock.updated` | Talhão atualizado |
| `pasture.measurement.recorded` | Nova medição registrada |
| `pasture.grazing.started` | Início de pastejo |
| `pasture.grazing.ended` | Fim de pastejo |
| `pasture.rest.started` | Início de descanso |
| `pasture.rest.completed` | Fim de descanso |

## Permissões

| Permissão | Descrição | Operações |
|-----------|-----------|-----------|
| `FARM_READ` | Leitura de dados | Visualizar talhões, medições, histórico |
| `FARM_OPERATE` | Operações básicas | Registrar medições, iniciar/encerrar pastejo |
| `FARM_MANAGE` | Gestão completa | Criar/editar/excluir talhões, configurar parâmetros |

## Integração com Autonomia Alimentar

O módulo Pasto Vivo fornece dados para o cálculo de autonomia alimentar:

- **Forragem disponível**: MSU estimada por talhão
- **Dias de autonomia**: baseado na taxa de consumo do rebanho
- **Recomendações**: quando repor ou rotacionar pastagens