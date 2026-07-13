# Pasto, colheita e silos — índice da arquitetura

Documentação de análise e proposta para a evolução incremental do WiNS Hub Agro. O código de referência foi o commit `84fcf70e15567ddc6c812d638c816204e5ae9035`, branch `master`, analisado em 13/07/2026. Nenhuma funcionalidade foi implementada nesta etapa.

## Como ler

1. [Contexto mestre](00_CONTEXT_MASTER.md): síntese executiva e decisões.
2. [Inventário atual](01_INVENTARIO_ATUAL.md): fatos confirmados no repositório.
3. [Visão de produto](02_VISAO_PRODUTO.md): ecossistema e princípios.
4. [Fontes gratuitas](03_FONTES_DADOS_GRATUITAS.md): matriz de viabilidade e restrições.
5. [Arquitetura](04_ARQUITETURA_PROPOSTA.md), [modelo conceitual](05_MODELO_DADOS_CONCEITUAL.md), [fórmulas](06_FORMULAS_E_PARAMETROS.md) e [ETL](07_APIS_JOBS_E_ETL.md).
6. [UX](08_UX_TELAS_E_FLUXOS.md) e detalhamento do [MVP](09_MVP_AUTONOMIA_ALIMENTAR.md).
7. Domínios: [Pasto Vivo](10_PASTO_VIVO.md), [colheita e silagem](11_COLHEITA_E_SILAGEM.md), [silos e armazenagem](12_SILOS_E_ARMAZENAGEM.md), [WiNS Hub Log](13_INTEGRACAO_WINS_HUB_LOG.md).
8. [Segurança](14_SEGURANCA_MULTIUSUARIO.md), [backlog](15_BACKLOG_PRIORIZADO.md), [critérios](16_CRITERIOS_DE_ACEITE.md), [riscos](17_RISCOS_LIMITACOES_E_DEPENDENCIAS.md).
9. [Checkpoint](18_CHECKPOINT_PARA_FUTURAS_SESSOES.md): retomada operacional curta.

## Legenda epistemológica

- **CONFIRMADO NO CÓDIGO**: observado no commit analisado; inclui caminho e linha aproximada.
- **PROPOSTA**: desenho futuro, ainda não implementado.
- **HIPÓTESE**: depende de descoberta ou validação de produto.
- **VALIDAÇÃO EXTERNA PENDENTE**: documentação, licença, acesso ou comportamento da fonte ainda não bastam para produção.
- **RISCO**: condição que pode causar dano, erro ou retrabalho.
- **DECISÃO RECOMENDADA**: escolha arquitetural sugerida para a próxima etapa.

Documentos comerciais e dossiês existentes foram tratados como contexto, não como prova de que uma função exista. Dados reais, `.env` e o banco de produção não foram consultados.
