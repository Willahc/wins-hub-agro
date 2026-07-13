# Critérios de aceite

Critérios são testáveis; valores de performance/retencão finais precisam baseline e decisão de produto.

## Dados, unidade e fórmulas

- [ ] Todo campo quantitativo exibe/recebe unidade; API rejeita unidade ausente/incompatível com `422`.
- [ ] Conversões MS/MV, kg/t, ha/m², saca e moeda têm testes de fronteira e arredondamento.
- [ ] Todo resultado persiste `formula_code`, `formula_version`, inputs/outputs e parâmetros resolvidos.
- [ ] Um run histórico é reproduzido sem usar parâmetros atuais.
- [ ] Valores `OBSERVED`, `USER_REPORTED`, `ESTIMATED`, `FORECAST`, `IMPORTED_OFFICIAL`, `DERIVED` e `BENCHMARK` não são confundidos.
- [ ] Fonte, competência/data de atualização e confiança aparecem em UI/PDF/API.
- [ ] Dado faltante retorna estado “indisponível/insuficiente”, nunca zero implícito.

## Segurança e isolamento

- [ ] Para cada rota/resource/export/anexo, testes com tenants A/B provam read/write/delete negados.
- [ ] Alterar `organization_id`, `farm_id`, `paddock_id`, `silo_id`, `animal_id` ou IDs filhos no payload não muda autorização.
- [ ] Membership revogada bloqueia nova requisição e sync offline.
- [ ] Mutação e auditoria confirmam/rollback juntas.
- [ ] Replay da mesma idempotency key retorna resultado anterior e não duplica ledger.
- [ ] Logs/erros não contêm segredo, cookie, contato real, CNPJ ou payload sensível.
- [ ] CSV neutraliza células iniciadas por `=`, `+`, `-`, `@`; anexos são privados e validados.
- [ ] Sessão/cookies/CSRF/headers atuais não sofrem regressão.

## Estoque e balanço

- [ ] Saldo é reconciliável pela soma de movimentos; ajuste cria movimento com motivo/aprovador.
- [ ] Transferência é atômica e balanceada; concorrência não gera saldo inválido.
- [ ] Demanda não conta o mesmo animal em lote manual e individual.
- [ ] Resultado mostra demanda, oferta, déficit/superávit, autonomia e data de ruptura em unidade correta.
- [ ] Cenário não altera saldo/rebanho até ação autorizada explícita.
- [ ] Golden cases aprovados por especialista coincidem dentro da tolerância documentada.
- [ ] Confiança mostra componentes e ação para melhorar o componente mais fraco.

## Geoespacial, clima e satélite

- [ ] Polígono inválido/CRS desconhecido é rejeitado; área geodésica e diferença declarada aparecem.
- [ ] Versão de geometria participa da chave da série.
- [ ] Cena/índice guarda algoritmo, cenas, cobertura válida, nuvem e período.
- [ ] Cobertura insuficiente não gera índice/alerta numérico enganoso.
- [ ] Medição de estação e estimativa de grade são rotuladas; distância/resolução/horário aparecem.
- [ ] Forecast mostra `issued_at` e `valid_at`; plano antigo não é reescrito por run novo.
- [ ] Recomendação remota contém “validar em campo” e não diagnostica definitivamente.

## Silos, colheita e regional

- [ ] Silo de silagem e grão têm fluxos/modelos distintos.
- [ ] Cálculo de silagem informa base MS/MV, perfil/densidade/perdas e confiança.
- [ ] Plano identifica horas, viagens, capacidade e gargalo; alterar um recurso recalcula o gargalo.
- [ ] Lote de grão preserva base de umidade; FIFO pode ser sobreposto só com justificativa/permissão.
- [ ] Capacidade Conab/SICARM aparece como “cadastrada/estática”, nunca “disponível”.
- [ ] Déficit/cobertura regional mostram anos, fontes e o termo “teórico”.
- [ ] Benchmark municipal informa que não comprova a produção da fazenda.

## UX e acessibilidade

- [ ] Desktop e larguras 360/768/1280 px não têm ação essencial inacessível/overflow destrutivo.
- [ ] Form controls têm label/nome acessível; foco visível; modal prende/restaura foco.
- [ ] Status/severidade não depende só de cor e atende contraste WCAG AA nos componentes críticos.
- [ ] Loading, vazio, parcial, vencido, erro e retry têm estados distintos.
- [ ] Teclado executa ações principais; mapa tem alternativa textual/lista.
- [ ] Permissão negada não é simulada apenas por botão oculto.

## Offline

- [ ] Item contém UUID, tenant/farm/device/user, captured_at, version, tentativas e erro/status.
- [ ] Troca de usuário/fazenda não mostra nem sincroniza fila anterior.
- [ ] Duplicata, timeout, 401/403, 409, erro permanente e dead-letter têm testes.
- [ ] Sincronização parcial não perde itens; conflito requer resolução explícita.
- [ ] Logout/revogação bloqueiam acesso local conforme política e não reatribuem evento.
- [ ] API privada não é armazenada genericamente pelo service worker.

## ETL, fallback e operação

- [ ] Adapter tem timeout, retry/backoff, rate limit, checkpoint e chave idempotente.
- [ ] Job interrompido retoma sem duplicar; promoção é transacional.
- [ ] Métricas registram freshness, contagens, rejeições, duração e erro por fonte.
- [ ] Fonte indisponível mostra último dado com idade ou “indisponível”; não inventa fallback.
- [ ] Mudança de schema/payload e dado revisado têm fixture/teste.
- [ ] CPU/RAM/disco do worker respeitam budget medido; API mantém objetivo de latência definido após baseline.
- [ ] Backup/restore do novo schema/storage é testado em ambiente não produtivo.

## Testes e regressão

- [ ] Unitários de domínio, integração repository/PostgreSQL efêmero, API/authz, template e E2E seletivo passam em ambiente isolado.
- [ ] Rotas Fazendas/Técnica/Mapa/Cruzamento/Campo/ROI mantêm smoke tests.
- [ ] Testes não acessam banco de produção nem serviços pagos.
- [ ] Fórmulas e contracts têm fixtures versionadas; alteração deliberada exige atualização/revisão.
- [ ] PDF/CSV reproduz filtro/run e aplica a mesma autorização da tela.

## Critérios de piloto

- [ ] Pelo menos dois papéis e dois tenants sintéticos exercitam o fluxo completo.
- [ ] Técnico aprova parâmetros/fontes e casos de referência documentados.
- [ ] Inventário físico e saldo têm divergência registrada, explicada e reconciliada.
- [ ] Todos os alertas piloto podem ser confirmados/descartados com motivo.
- [ ] Incidente de fonte/worker/offline é simulado e recuperado sem perda/duplicação.
- [ ] Termos/licenças das fontes habilitadas estão revisados e atribuídos.
