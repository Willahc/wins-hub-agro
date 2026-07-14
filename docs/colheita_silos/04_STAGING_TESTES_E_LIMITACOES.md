# Staging, testes e limitações

```bash
bash scripts/fase0d/start_staging.sh
bash scripts/fase4_colheita_silos/apply_staging.sh
STAGING_TEST=1 bash scripts/fase4_colheita_silos/test_http.sh
STAGING_TEST=1 bash scripts/fase4_colheita_silos/test_ui.sh
```

O seed idempotente cria quatro planos: capacidade adequada, próximo do limite, acima da capacidade e concluído com lote vinculado.

Limitações do MVP: não há mapa de talhões, recomendação automática de produtividade nem reserva física de capacidade entre planos concorrentes. A capacidade é um snapshot no planejamento e é obrigatoriamente revalidada na conclusão. Estruturas sem capacidade cadastrada podem ser planejadas, mas exigem confirmação operacional.

Produção não recebe migration, flag, restart ou deploy nesta fase. Todos os testes HTTP usam somente `127.0.0.1:18080`.
