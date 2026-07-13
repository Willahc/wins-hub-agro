# Autonomia Alimentar — Limitações e Próximos Passos

## Limitações do MVP

### Cálculo
- Assume consumo constante (sem variação sazonal ou por condition)
- Não considera recuperação de pasto após utilização
- Não inclui perdas de armazenamento por período
- Não calcula custo por kg MS ou por animal

### Dados
- Entrada manual (sem integração com inventário de campo)
- Sem validação com dados reais de produção
- Sem conexão com sensores ou satélite
- Sem histórico de pesagens automáticas

### Interface
- Sem gráficos (apenas barra de progresso CSS)
- Sem exportação PDF
- Sem notificações
- Sem modo offline

### Segurança
- Sem idempotência na criação (pode criar duplicatas)
- Sem rate limiting por endpoint
- Sem auditoria detalhada de cada campo alterado

## Próximos passos

### Curto prazo (Fase 1.1)
- [ ] Gráfico de composição do estoque (SVG simples)
- [ ] Exportação CSV dos cenários
- [ ] Validação de duplicatas (nome + fazenda + data)
- [ ] Rate limiting nos endpoints de escrita
- [ ] Testes de idempotência

### Médio prazo (Fase 1.2)
- [ ] Integração com inventário de campo (App de Campo)
- [ ] Cálculo de custo por kg MS
- [ ] Alertas automáticos (WhatsApp/e-mail)
- [ ] Cenários com recuperação de pasto
- [ ] Exportação PDF

### Longo prazo (Fase 2+)
- [ ] Integração com dados de satélite (NDVI)
- [ ] Previsão climática
- [ ] Otimização automática de dieta
- [ ] Integração com WiNS Hub Log
- [ ] App offline

## Decisões de produto

- **Não migrar automaticamente** os 5 usuários legados
- **Cadastro manual** em etapa futura
- **Staging isolado** — produção intocada
- **Feature flag default false** — ativação explícita
