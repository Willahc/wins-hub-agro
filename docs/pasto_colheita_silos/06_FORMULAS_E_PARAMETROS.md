# Fórmulas e parâmetros

## Princípio

As fórmulas abaixo são especificações candidatas, não recomendações técnicas definitivas. Cada implementação terá código/versão, unidade de entrada/saída, parâmetros com vigência, fonte técnica, aprovador, testes e snapshot. Nenhum coeficiente agronômico/zootécnico será universal.

## Geometria, pasto e satélite

| Cálculo | Entradas e unidade | Saída/expressão candidata | Premissas, erros e validação/confiança |
|---|---|---|---|
| Área por geometria | polígono CRS conhecido | `area_geodesica / 10.000` ha | geometria válida, não usar graus²; comparar área declarada; erro de limite/GPS |
| Oferta bruta de MS | área ha × massa kg MS/ha | kg MS | massa varia no espaço/tempo; amostragem de campo |
| Oferta utilizável | oferta bruta × taxa utilização | kg MS | taxa configurável por sistema/manejo; perdas separadas |
| Índice de vigor | índice(s), cobertura válida, período | score 0–100 por normalização versionada | não equivale biomassa/diagnóstico; sensor, nuvem, solo e sazonalidade |
| Anomalia | valor atual e baseline sazonal | `(atual - mediana_hist) / dispersão` ou % | mínimo histórico, mesma janela; documentar robustez |
| Tendência | série 30/60/90 dias | inclinação/% versionada | cobertura temporal e outliers; intervalo de confiança |
| Cobertura irregular | pixels/classes dentro do polígono | ha e % | limiar/modelo versionado; precisão limitada pela resolução |
| Confiança remota | pixels válidos, nuvem, recência, concordância de fontes/visita | 0–100 | modelo de confiança auditável; não “probabilidade de diagnóstico” |

## Demanda e balanço forrageiro

| Cálculo | Entradas | Saída candidata | Limites/premissas |
|---|---|---|---|
| Demanda MS por lote | cabeças × peso médio kg × consumo `% PV/dia` | kg MS/dia | categoria/fase/produção/clima alteram consumo; especialista configura |
| Demanda total | soma lotes válidos | kg MS/dia/mês | evitar dupla contagem de animais; `as_of` explícito |
| Estoque de MS | massa natural kg × MS% | kg MS | amostra/data/base de matéria; incerteza da pesagem |
| Estoque útil | estoque MS × `(1 - perdas armazenamento - perdas retirada - perdas cocho)` | kg MS útil | decidir composição multiplicativa/aditiva com especialista; não permitir perda >100% |
| Oferta diária de pasto | oferta utilizável ÷ horizonte/rotação | kg MS/dia | recuperação não é linear por padrão |
| Déficit/superávit | oferta diária − demanda diária | kg MS/dia, sinal | mostrar ambos com convenção clara |
| Autonomia simples | estoque útil ÷ consumo/déficit aplicável | dias | se demanda variável, usar simulação diária; divisão por zero tratada |
| Curva projetada | `saldo[d+1]=saldo[d]+entradas-oferta_consumida-perdas` | kg MS por dia/data ruptura | cenários e recuperação versionados |
| Data de término | primeira data com saldo < margem segurança | date | timezone/data base e margem explícitos |

**DECISÃO RECOMENDADA** — MVP calcula por dia, mesmo que demanda constante, para suportar entradas, recuperação e cenários sem trocar a semântica depois.

## Silagem e feno

| Cálculo | Entradas | Saída | Premissas/erros |
|---|---|---|---|
| Volume silo retangular | comprimento × largura × altura × fator de perfil | m³ | perfil/trincheira pode exigir seção trapezoidal e topografia |
| Volume trapezoidal | comprimento × altura × `(largura_base+largura_top)/2` | m³ | forma regular; medir em vários pontos se irregular |
| Massa verde | volume m³ × densidade kg/m³ | kg/t MV | densidade depende de MS/compactação/cultura |
| Massa seca | massa verde × MS% | kg/t MS | análise/amostra e data obrigatórias |
| Silagem útil | massa seca × `(1 - perdas)` | kg MS útil | perdas por fase parametrizadas; não misturar MV e MS |
| Retirada diária | soma movimentos de saída por data | kg MV e kg MS/dia | MS snapshot do lote no movimento |
| Autonomia silo | saldo útil / demanda atribuída | dias | destinos/lotes definidos; curva quando consumo varia |
| Custo diário | retirado × custo por unidade + custos operacionais | BRL/dia | método de custeio versionado |
| Custo por animal | custo período / animal-dia | BRL/animal/dia | cabeça-dia, não apenas cabeça final |
| Custo/kg MS | custo atribuível / kg MS útil consumida | BRL/kg MS | perdas e rateio explícitos |

## Grãos e armazenagem

| Cálculo | Entradas | Saída | Premissas/erros |
|---|---|---|---|
| Capacidade livre | capacidade útil − estoque equivalente | t | produto/densidade/compartimentos compatíveis |
| Ocupação | estoque / capacidade útil × 100 | % | capacidade útil vigente |
| Correção por umidade | peso e umidade inicial/final | massa corrigida por balanço de matéria seca | fórmula aprovada por produto/contrato; impureza separada |
| Quebra técnica | entrada corrigida − saídas − saldo corrigido | t/% | reconciliação por lote/período; pode ser erro de medição |
| Perda estimada | estoque base × taxa/período/modelo | t e valor | rotular estimada; não lançar ledger sem confirmação |
| FIFO | ordenar lotes elegíveis por entrada/validade | sequência | qualidade/bloqueio pode sobrepor FIFO com justificativa |
| Custo/t | secagem+aeração+armazenagem+perdas+movimentação / t útil | BRL/t | método e janela de rateio explícitos |
| Vender x armazenar | receita futura esperada − custos/riscos vs receita atual | BRL/intervalo | preço futuro é cenário, não promessa; impostos/frete configuráveis |

## Colheita e logística

| Cálculo | Entradas | Saída | Premissas/erros |
|---|---|---|---|
| Produtividade | produção corrigida / área colhida | kg/ha, t/ha ou sc/ha | saca com peso explícito; umidade/base |
| Produção esperada | área × produtividade em cenários | faixa t | não apresentar valor pontual sem incerteza |
| Horas de máquina | área / capacidade operacional efetiva ha/h | h | capacidade considera largura, velocidade e eficiência |
| Viagens | `ceil(massa / capacidade útil veículo)` | viagens | limites legais, densidade e ciclo |
| Frota simultânea | fluxo colhedora/recebimento × tempo de ciclo | veículos | filas/estrada/descarga variam |
| Capacidade necessária de silo | massa verde / densidade × margem/perdas | m³ | perfil, compactação e pico diário |
| Gargalo diário | `min(colheita, transporte, recepção, armazenagem)` | t/dia e recurso limitante | disponibilidade por turno e paradas |
| Janela operacional | interseção maturação, clima, solo, recursos, capacidade | intervalo + score/risco | previsão muda; recalcular e mostrar run |
| Custo de transporte | distância/rota × tarifa + espera/pedágio/retorno | BRL/t, BRL/viagem | contrato/rota real; nunca afirmar sem fonte |

## Regional e benchmark

| Cálculo | Entradas | Saída | Advertência |
|---|---|---|---|
| Cobertura de armazenagem | capacidade estática cadastrada / produção do mesmo escopo/período | % | não é ocupação nem disponibilidade |
| Déficit teórico | `max(produção - capacidade, 0)` | t | produção e capacidade podem ter datas/metodologias distintas |
| Pressão de armazenagem | função versionada de cobertura, concentração, sazonalidade, distância | classe/score | índice explicável; calibrar com histórico |
| Benchmark de produtividade | `(fazenda - municipal)/municipal × 100` | % | valor da fazenda informado; média municipal não comprova produção |

## Clima e risco

- chuva acumulada: soma de precipitação válida no período; registrar cobertura/faltantes;
- dias sem chuva: dias consecutivos abaixo de limiar configurável, não necessariamente zero;
- graus-dia: soma diária de função limitada por temperaturas base/teto específicas da cultura;
- balanço hídrico: precipitação + armazenamento anterior − evapotranspiração − escoamento/drenagem, com modelo/solo versionados;
- THI/conforto bovino: fórmula e faixas por categoria/condição, validadas por especialista;
- risco de incêndio, geada, entrada de máquina, pulverização, fenação e ensilagem: regras multicritério com validade/forecast run, nunca certeza.

## Parâmetros

Hierarquia de resolução: padrão publicado → organização → fazenda → unidade/piquete/lote → cenário. A resolução grava a origem de cada valor. Exemplos: consumo `% PV`, MS, utilização, massa de forragem, densidade, perdas, margem, recuperação, produtividade, eficiência de máquina, capacidade de veículo e limites de alerta.

Parâmetros publicados são imutáveis; alteração cria versão/vigência. Cenário pode sobrescrever temporariamente sem mudar configuração operacional.

## Testes das fórmulas

- golden cases aprovados por especialista, com unidades;
- propriedades: não negatividade, conservação de massa, monotonicidade onde válida;
- fronteiras: zero, nulo, 100%, datas, troca de unidade e arredondamento;
- reprodução de run histórico a partir do snapshot;
- comparação paralela ao cálculo manual no piloto;
- teste de incerteza/cenários, sem comparar apenas string de implementação.
