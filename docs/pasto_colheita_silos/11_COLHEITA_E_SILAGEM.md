# Colheita, feno e silagem

## Objetivo

Transformar maturidade estimada, clima e capacidade operacional em um plano diário explicável de colheita, fenação ou ensilagem, conectado ao destino e ao estoque.

## Planejamento

Entradas: cultura/cultivar, área, datas, ciclo/finalidade, produtividade/faixa, umidade/MS alvo, observação de maturidade, máquinas/turnos, veículos/ciclo, recepção e silo. Cada entrada informa unidade, fonte, data e se é observada, informada, oficial ou estimada.

Saídas:

- estágio e graus-dia estimados;
- janela provável de maturação e janela operacional recomendada;
- chuva/dias secos/risco de solo úmido;
- faixa de produção, horas, viagens, fluxo/dia e volume;
- recurso limitante e capacidade adicional necessária;
- plano diário e alertas de atraso.

**RISCO** — graus-dia/ZARC/previsão não substituem maturidade ou teor de MS observado. O plano deve ter botão “atualizar observação” e recalcular.

## Motor de janela

1. Estimar intervalo fenológico com parâmetros por cultivar/fonte.
2. Aplicar observação de campo como evidência mais recente, sem apagar estimativa.
3. Obter forecast run e classificar cada dia por critérios parametrizados.
4. Calcular capacidade de colheita, transporte, descarga/compactação/recepção.
5. Identificar `min(capacidades)` e simular fila/ciclo.
6. Gerar cenários provável/conservador/otimista.
7. Congelar plano aprovado; revisões criam nova versão.

## Silagem

O fluxo fecha o balanço de massa:

```text
plantio → colheita (massa verde/MS) → transporte → silo/lote
        → fermentação/perdas → abertura → retirada → lote animal → balanço alimentar
```

Cadastro de silo: trincheira, superfície, bolsa, torre/outro; perfil/dimensões/coordenada. Lote: cultura/híbrido, plantio/corte/fechamento/abertura, MS, massa, densidade/compactação, inoculante, custos e perdas. Retirada sempre registra massa natural e snapshot de MS; destino é lote/local autorizado.

Medições por dimensões/foto são estimativas, com método/confiança. Inventário físico não reescreve saldo; gera proposta de ajuste com motivo e aprovação.

## Feno

Planejar corte, secagem, revolvimento/enleiramento, enfardamento e armazenagem. Entradas incluem umidade, chuva/UR/vento, capacidade de máquinas e peso médio do fardo. Estoque por lote e movimentação, com MS, perdas, condição e custo. “Condição para fenação” é regra explicável e atualizada, não garantia.

## Exemplo de saída

> Milho para silagem — 42 ha. Janela provável 18–24/08; melhor janela operacional 19–21/08 no forecast emitido em …; risco de chuva baixo e de solo úmido moderado. Produção estimada 1.470–1.720 t, 74–86 viagens e 2.100–2.450 m³. Gargalo provável: compactação/recebimento. Validar MS e trafegabilidade em campo.

Valores são ilustrativos; a aplicação nunca os usa como defaults.

## Alertas

- maturidade/janela próxima sem plano aprovado;
- chuva prevista durante operação;
- dias secos insuficientes para feno;
- solo provavelmente úmido;
- capacidade de máquina/transporte/recepção abaixo do fluxo;
- silo insuficiente ou lote incompatível;
- compactação/fechamento atrasados;
- produção real fora da faixa;
- silagem termina antes da recuperação prevista.

## Integrações

- clima e ZARC via adapters versionados;
- talhão/safra e observação de Campo;
- silagem alimenta ledger/autonomia após confirmação de entrada;
- recursos de transporte podem gerar solicitação ao Log, sem reserva implícita;
- PDF apresenta versão do forecast e premissas.

## Testes

- conservação de massa e conversão MS/MV;
- `ceil` de viagens e capacidade de pico;
- gargalo muda quando recurso muda;
- plano antigo permanece reproduzível após novo forecast;
- datas/ciclo/timezone e janela vazia;
- concorrência/versionamento de plano;
- permissão entre fazendas/organizações;
- telas mobile/offline para observação/execução.

## Fora da primeira versão

Telemetria de máquina, controle autônomo, roteirização dinâmica, previsão proprietária e otimização global. A primeira versão recebe capacidade e tempos informados e mede divergência para calibrar.
