# 03 — Guia do Usuário do Pasto Vivo

## Visão Geral

O módulo Pasto Vivo permite gerenciar pastagens de forma simples e eficiente. Este guia explica como usar cada funcionalidade.

## 1. Cadastrando Talhões

### Passo a passo

1. Acesse **Pasto Vivo → Talhões** no menu lateral
2. Clique em **Novo Talhão**
3. Preencha os campos:
   - **Nome**: Identificação do talhão (ex: "Talhão Norte")
   - **Área**: Tamanho em hectares
   - **Forrageira**: Tipo de capim (Brachiaria, Panicum, etc.)
   - **Fator de Conversão**: Geralmente 120 para Brachiaria
   - **Altura de Descanso**: Altura mínima para descanso (padrão: 10 cm)
   - **Taxa de Crescimento**: cm/dia (varia com a estação)
4. Clique em **Salvar**

### Dicas

- Use nomes descritivos para facilitar a identificação
- O fator de conversão pode ser ajustado com base em análises locais
- A taxa de crescimento varia: verão ~2 cm/dia, inverno ~0.5 cm/dia

## 2. Registrando Medições

### Por que medir?

Medições regulares são essenciais para:
- Conhecer a produtividade da pastagem
- Tomar decisões de lotação
- Evitar o superpastejo

### Como medir

1. Selecione o talhão desejado
2. Clique em **Nova Medição**
3. Informe:
   - **Data**: Data da medição (geralmente hoje)
   - **Altura**: Use trena ou estaca graduada
   - **Cobertura**: Estime a porcentagem de solo coberto por vegetação
4. O sistema calcula automaticamente a biomassa estimada
5. Adicione observações se necessário (ex: "após chuva", "comprimento desigual")

### Altura x Cobertura

| Altura (cm) | Cobertura (%) | Biomassa Estimada (kg/ha) |
|-------------|---------------|---------------------------|
| 10 | 60 | 720 |
| 15 | 70 | 1260 |
| 20 | 80 | 1920 |
| 25 | 85 | 2550 |
| 30 | 90 | 3240 |

*Valores para Brachiaria (fator = 120)*

## 3. Gerenciando Pastejo

### Iniciar pastejo

1. Selecione o talhão em estado **DISPONÍVEL**
2. Clique em **Iniciar Pastejo**
3. Informe:
   - **Número de animais**
   - **Tipo de animal** (Bovino, Ovino, etc.)
   - **Peso médio** (kg)
   - **Observações**
4. O sistema calcula automaticamente a lotação (UI/ha)

### Encerrar pastejo

1. Acesse o talhão em estado **EM_PASTEJO**
2. Clique em **Encerrar Pastejo**
3. Registre o motivo (ex: "atingimento do ponto de corte", "mudança de área")

### Monitorar pastejo

No dashboard, você pode ver:
- **Dias pastando**: Tempo desde o início
- **Consumo estimado**: Baseado na lotação
- **Estado do pasto**: Se está dentro dos limites

## 4. Interpretando Estados

### DISPONÍVEL

- Pasto em condições adequadas para pastejo
- Altura acima do ponto de corte
- Pode receber animais

### EM_PASTEJO

- Animais estão pastando na área
- Monitorar diariamente
- Verificar se a altura está dentro do esperado

### EM_DESCANSO

- Área em repouso para recuperação
- NÃO inserir animais (exceto emergência)
- Aguardar atingir a altura de repouso

### Alertas Comuns

| Alerta | Significação | Ação |
|--------|--------------|------|
| Medição expirada | Dados com mais de 7 dias | Nova medição obrigatória |
| Altura abaixo do corte | Pasto muito curto | Remover animais |
| Descanso insuficiente | Tempo de descanso menor que o necessário | Aguardar ou ajustar |
| Lotação alta | Muitos animais para a área | Reduzir carga |

## 5. Usando o Dashboard

### Visão Geral

O dashboard mostra em uma página:
- **Total de talhões**: Quantos talhões estão cadastrados
- **Por estado**: Quantos em cada situação
- **Área total**: Somatório de hectares
- **Cobertura média**: Estado geral das pastagens
- **Alertas**: Itens que precisam de atenção

### Filtros

- **Por fazenda**: Visualizar apenas talhões de uma fazenda
- **Por estado**: Filtrar por DISPONÍVEL, EM_PASTEJO ou EM_DESCANSO
- **Por forrageira**: Filtrar por tipo de capim

### Gráficos

- **Evolução da cobertura**: Como a pastagem está se recuperando
- **Dias de descanso**: Tempo de descanso por talhão
- **Produtividade**: Biomassa produzida por hectare

## 6. Importando para Autonomia Alimentar

### Como exportar dados

1. Acesse **Pasto Vivo → Integração**
2. Selecione a fazenda e data de referência
3. Clique em **Exportar para Autonomia Alimentar**
4. Os dados serão enviados automaticamente para o módulo de nutrição

### Dados exportados

- Biomassa disponível por talhão
- Dias de autonomia estimados
- Recomendações de manejo

### Uso no Autonomia Alimentar

No módulo de Autonomia Alimentar:
1. Os dados de pastagem aparecem em **Fontes de Alimentação**
2. O sistema calcula automaticamente a contribuição da pastagem
3. Você pode ajustar percentuais conforme necessário

## Glossário

| Termo | Definição |
|-------|-----------|
| **Talhão** | Área de pastagem delimitada para manejo |
| **Forrageira** | Tipo de planta utilizada para pastejo |
| **Biomassa** | Quantidade de material vegetal por área |
| **MS (Matéria Seca)** | Parte sólida da planta, sem água |
| **MSU (Matéria Seca Utilizável)** | Parte da MS que o animal pode consumir |
| **UI/ha** | Unidades de Animal por Hectare |
| **Lotação** | Quantidade de animais por área |
| **Descanso** | Período sem pastejo para recuperação da pastagem |
| **Ponto de corte** | Altura mínima para retirada dos animais |
| **Fator de conversão** | Multiplicador para estimar biomassa a partir da altura |

## Dicas para o Dia a Dia

1. **Mede regularmente**: A cada 7 dias no mínimo
2. **Anotar observações**: Tempo, condições do solo, estado dos animais
3. **Respeitar o descanso**: Pasto descansado produz mais
4. **Monitorar alertas**: Verifique o dashboard diariamente
5. **Ajustar lotação**: Nem sempre a mesma quantidade de animais é adequada
6. **Considerar a estação**: Crescimento varia com chuva e temperatura

## Problemas Comuns

### "Não sei quando medir"
- Medir sempre no mesmo dia da semana
- Criar rotina: toda segunda-feira, por exemplo

### "O pasto não cresce"
- Verificar se há compactação do solo
- Considerar adubação
- Avaliar se a altura de corte está adequada

### "Animais magros"
- Verificar se a lotação está adequada
- Avaliar a qualidade da forragem
- Considerar suplementação

### "Não consigo ver os dados"
- Verifique se a feature flag está ativada
- Confirme suas permissões de acesso
- Atualize a página