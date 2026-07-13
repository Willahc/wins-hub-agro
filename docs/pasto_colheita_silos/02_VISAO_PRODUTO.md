# Visão de produto

## Tese

**PROPOSTA** — evoluir o WiNS Hub Agro de inteligência genética/comercial para uma camada de decisão operacional que una rebanho, alimento, área, clima, colheita, estoque e logística. O valor não está em um índice isolado, e sim em transformar dados heterogêneos em decisões rastreáveis.

## Princípios de produto

1. **Manual primeiro, automação depois:** o MVP precisa entregar autonomia com informação informada e auditável.
2. **Uma verdade operacional, várias evidências:** saldo/movimentação do usuário difere de estimativa remota ou benchmark oficial.
3. **Explicabilidade na tela:** “como calculamos”, entradas, unidades, versão, fonte, data e confiança.
4. **Incerteza visível:** intervalos e cenários substituem precisão artificial.
5. **Validação humana:** satélite/clima gera sinal e prioridade; técnico confirma campo.
6. **Fazenda como escopo:** toda ação nasce vinculada a organização e fazenda autorizadas.
7. **Offline seletivo:** captura essencial funciona offline; mapas/rasters e análises pesadas não precisam.

## Módulos e relações

```text
Rebanho + lotes ──> demanda de MS ─────────────┐
Piquetes/pasto ───> oferta estimada de MS ─────┤
Silagem/feno/suplemento ──> estoque útil ──────┼─> balanço, autonomia, cenário, alerta
Clima + campo + satélite ──> recuperação/risco ┘

Safra + clima ──> janela de colheita ──> máquinas + viagens ──> silo
Produção municipal + capacidade cadastrada ──> pressão regional (não ocupação real)
Plano logístico aprovado ──> contrato API ──> WiNS Hub Log
```

## Pasto Vivo

Cadastro de limites/talhões/piquetes, observações e séries temporais. Compara vigor e tendência, mostra chuva e risco, e prioriza visitas. “Provável degradação” exige validação em campo; índice remoto nunca altera automaticamente estoque de forragem.

## Autonomia e balanço

Agrega demanda de MS por lote e oferta útil de pasto/estoques. Exibe cenário provável, conservador e otimista, data de ruptura e custo de cobertura. Simulações são separadas do operacional até serem aplicadas por ação explícita.

## Clima agrícola

Une estação observada, dado de grade e previsão, identificados separadamente. Suporta chuva, seca, calor bovino, incêndio e janelas operacionais. Aptidão para pulverizar/fenar/ensilar é orientação parametrizada, não garantia.

## Colheita, feno e silagem

Planeja janela provável, capacidade de máquina, transporte e recebimento. Calcula faixas de produção/viagens/volume e sinaliza gargalos. A decisão final incorpora observação de maturidade e condição local.

## Silos

- **Silo de silagem:** geometria/volume, massa verde/MS, compactação, perdas, abertura, retirada, destino e autonomia alimentar.
- **Silo de grãos:** unidade, capacidade, lote, entrada/saída/transferência, umidade, temperatura, secagem, aeração, perda, custo e rastreabilidade.

Não compartilhar uma única entidade “silo” cheia de campos opcionais; usar estrutura física comum apenas se o domínio justificar, com subtipos separados.

## Armazenagem e inteligência municipal

Mapa de unidades externas mostra cadastro, serviços, distância e fonte. Disponibilidade em tempo real só aparece quando confirmada por integração ou atualização do fornecedor. Radar cruza produção oficial com capacidade estática para um **déficit teórico**, nunca ocupação real. Benchmark municipal compara valores informados, com ano/unidade/fonte.

## Personas e decisões

| Persona | Decisão | Necessidade |
|---|---|---|
| Gestor/proprietário | vender, suplementar, colher, armazenar | visão consolidada, cenário e custo |
| Encarregado | mover lote, retirar alimento, inspecionar silo | fluxo móvel simples e offline |
| Técnico | validar pasto, parâmetros e recomendação | evidência, histórico e auditoria |
| Administrativo | estoque, custo, exportação | ledger, fechamento e rastreabilidade |
| Leitura/consultor | acompanhar sem editar | escopo e exportação controlados |

## Métricas de valor

- percentual de fazendas com demanda e estoque completos;
- dias de antecedência de alerta de ruptura;
- divergência inventário calculado versus medido;
- cenários avaliados e decisões aplicadas;
- alertas validados/descartados com motivo;
- redução de perdas informadas por MS/tonelada;
- planos de colheita sem gargalo de recebimento;
- cobertura de observações por piquete.

**RISCO** — métricas de adoção não provam causalidade econômica. Benefício financeiro deve ter baseline e hipótese explícita.

## Fora de escopo inicial

- diagnóstico automatizado de degradação, doença ou produtividade;
- comando de máquinas/sensores;
- disponibilidade real de armazéns sem integração;
- roteirização/frete transacional dentro do Agro;
- processamento nacional contínuo de imagens na VPS;
- recomendação agronômica universal hardcoded.
