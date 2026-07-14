# Colheita e Silos

Módulo de planejamento de corte, estimativa de matéria natural e seca, alocação da produção em estruturas do módulo Silagem e Estoques e conversão atômica do resultado real em lotes.

- Feature flag: `ENABLE_HARVEST_SILOS` (desligada por padrão; ativa no staging).
- Regra de cálculo: `harvest_silos.v1`.
- Banco: schema `harvest`, sem duplicar o cadastro `storage.feed_storage_facilities`.
- Interface: `/colheita-silos`.
- API: `/api/v2/farms/{farm_uuid}/harvest-silos`.

Documentos: [regras](01_ESCOPO_CALCULOS_E_REGRAS.md), [dados e API](02_MODELO_DADOS_E_API.md), [guia](03_GUIA_USUARIO.md) e [staging](04_STAGING_TESTES_E_LIMITACOES.md).

## Integrações

- **Clima e Operações**: Previsão durante o período de cada plano de colheita
