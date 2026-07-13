# MVP — Autonomia Alimentar + Estoque de Silagem

## Objetivo e hipótese

Responder, com entradas manuais auditáveis: “por quantos dias esta fazenda alimenta o rebanho e quais ações merecem avaliação?”.

**HIPÓTESE** — gestores aceitarão registrar/reconciliar estoques se o resultado mostrar ruptura, cenários e custo de forma simples. Medir no piloto; não assumir.

## Dependência obrigatória

Fase 0 mínima: organização/membership/fazenda, policies por recurso, usuário persistente, auditoria transacional, unidades, parâmetro/fórmula versionados e banco de teste. Sem isso, o MVP não está pronto para múltiplos clientes.

## Escopo

- fazenda e lotes/rebanho atuais;
- quantidade, categoria, peso médio e consumo configurável;
- disponibilidade manual de pasto e taxa de utilização;
- silagem, feno, suplemento, MS, perdas, saldo e custo;
- demanda/oferta/déficit/superávit/autonomia/ruptura;
- cenários sem efeitos operacionais;
- alertas explicáveis;
- PDF e capturas offline selecionadas.

Fora: satélite, sensor, previsão automática, compras, financeiro contábil, otimização matemática de dieta e recomendação veterinária/nutricional.

## Reuso do atual

- `fazenda.cliente` como origem a mapear para `farm`, sem assumir equivalência definitiva;
- grupos/animais/pesagens (`app/main.py`, linhas 3.865–4.548 e 4.978–5.023);
- shell/base e padrões de cards;
- outbox UUID/retry como referência (`campo.html`, linhas 986–1.160);
- PDF/WeasyPrint;
- ROI Pasto Limpo como link/contexto, sem acoplar fórmula.

## Dados e precedência

1. Animal ativo individual com pesagem válida; se ausente, lote informado.
2. Snapshot do rebanho no instante do run; alterações posteriores não reescrevem o run.
3. Estoque vem do ledger. Saldo inicial é movimento `OPENING_BALANCE` aprovado.
4. MS/perdas guardadas no lote e copiadas para movimento/cálculo.
5. Pasto informado/observado mantém método/data/confiança.

Não somar animal individual e quantidade manual do mesmo lote. A UI mostra reconciliação.

## Caso de uso principal

1. Gestor escolhe fazenda autorizada.
2. Sistema monta snapshot de lotes, destacando peso/categoria ausentes ou antigos.
3. Usuário confirma consumo `% PV` por lote e sua fonte.
4. Informa piquete/área/massa de forragem/taxa de utilização ou oferta diária manual.
5. Cadastra estoque: localização, alimento, massa natural, MS, perdas, custo e data.
6. Revisão apresenta conversões e fontes; campos críticos não têm defaults silenciosos.
7. Motor diário executa cenário provável e, opcionalmente, conservador/otimista.
8. Resultado salva `formula_run`, `feed_balance_run`, confiança e inputs.
9. Alerta é gerado por regra versionada; PDF reproduz o snapshot.

## Motor do MVP

Para cada dia do horizonte:

```text
demanda_lote = cabeças × peso_médio_kg × consumo_pct_PV
demanda_total = soma(demanda_lote)
oferta_pasto_util = oferta_bruta × utilização
déficit_pós_pasto = max(demanda_total - oferta_pasto_util, 0)
estoque[d+1] = estoque[d] + entradas - alimento_consumido - perdas_eventuais
ruptura = primeiro dia em que oferta < demanda + margem
```

A prioridade de consumo entre pasto/silagem/feno/suplemento é um parâmetro/cenário, não uma decisão implícita. Fórmulas completas seguem `06`.

## Confiança

Score explicável por componente, sem mascarar falta de dado:

- rebanho: cobertura e recência do peso;
- consumo: fonte/especificidade do parâmetro;
- pasto: método, amostra, recência e variabilidade;
- estoque: medição versus estimativa, MS e reconciliação;
- projeção: horizonte e premissas de recuperação.

Mostrar componente mais fraco e ação para melhorar. O score não é precisão estatística sem calibração.

## Cenários

- reduzir lotação/vender/transferir animais;
- trocar lote/piquete;
- alterar utilização/consumo/perda/recuperação;
- comprar suplemento/adicionar feno/silagem;
- planejar nova produção de silagem;
- alterar custo.

O cenário guarda delta sobre o run-base. “Aplicar” abre uma confirmação e cria os comandos/movimentos autorizados correspondentes; nunca reescreve históricos.

## Alertas MVP

| Alerta | Regra candidata | Ação sugerida |
|---|---|---|
| autonomia baixa | dias < limite da fazenda | revisar estoque/parâmetros e avaliar cenário |
| déficit diário | demanda > oferta | avaliar suplementação/lotação |
| silagem termina antes da recuperação | fim estimado < recuperação | validar pasto e plano de cobertura |
| dado fraco | confiança/completude < limite | medir/reconciliar campo |
| estoque inconsistente | saldo/medição diverge | inventário e ajuste com motivo |
| parâmetro vencido | vigência/fonte expirada | técnico revisar |

## APIs e telas

- `/feed/setup-status`, `/feed/items`, `/feed/locations`, `/feed/movements`;
- `/herd/snapshot`, `/feed/balance-runs`, `/feed/scenarios`, `/alerts`;
- telas: Visão geral, Autonomia wizard, Estoques, Silo de silagem, Cenários e Alertas;
- Campo: inventário, retirada de silagem, observação de pasto e conflito de sync.

## Segurança

- toda consulta/mutação recebe `ActorContext` e farm autorizada;
- ID fora do tenant retorna 404/403 padronizado;
- `Idempotency-Key` unique por organização;
- ajuste e parâmetro crítico exigem papel/motivo;
- export/PDF/anexo aplica policy e `no-store`;
- auditoria atômica com movimento/aprovação;
- offline particionado, protegido e limpo após revogação/logout conforme política.

## Estratégia de teste

1. Unitários do domínio com golden cases/unidades/propriedades.
2. Repository com PostgreSQL efêmero, constraints e tenants A/B.
3. API: auth, roles, IDOR, idempotência, conflito, validação.
4. Template/acessibilidade/responsividade e estados vazios/erro.
5. Offline: duplicate, retry, dead-letter, troca de usuário, revogação.
6. PDF reproduz o run e não vaza outro tenant.
7. Regressão das rotas existentes/ROI/Campo.

## Rollout

- shadow calculation com planilha/manual do técnico;
- uma organização e poucas fazendas piloto;
- reconciliar estoque e diferenças diariamente na primeira janela;
- registrar alteração de parâmetros e feedback;
- habilitar alertas como informativos, depois operacionais;
- expandir somente após critérios de isolamento, reprodução e qualidade.

## Critério de pronto para piloto

- 100% dos acessos testados entre tenants negados;
- run reproduzível pela versão/snapshot;
- nenhuma unidade implícita;
- saldo reconciliável por ledger;
- cálculo manual aprovado em casos de referência;
- incerteza e fonte visíveis;
- fila offline não mistura usuários/fazendas;
- backup/restore do novo schema testado fora da produção.
