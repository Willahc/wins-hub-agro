# Checkpoint Fase 0A

Base: `master` em `e5b131c5360bb566939f4aa43621c05eec5a70a0`, inicialmente limpo e alinhado a
`origin/master`.

**IMPLEMENTADO NESTA ETAPA:** `app/core`, `app/domain`, repository, schema HTTP,
router privado, SQL em `scripts/fase0`, testes `test_fase0*` e esta documentação.
Única integração no monolito: include condicional do router, desligado por padrão.

**DECISÕES:** fazenda operacional separada de prospecção; UUID externo; FK composta;
deny-by-default; 404 cross-tenant; Decimal; unidades dimensionais; registry sem eval;
auditoria transacional; SQL versionado e não aplicado.

**LIMITAÇÕES:** usuários/dados atuais não foram mapeados; resource resolver suporta
apenas a fazenda nova no repository real; endpoints legados continuam pendentes;
sem UI, RLS, backfill ou integração PostgreSQL.

Próximo passo: Fase 0B em ambiente isolado — revisão DBA e teste PostgreSQL 16,
processo de bootstrap idempotente, mapeamento explícito `fazenda.cliente` →
operational farm e migração de uma operação legada de baixo risco.

## Atualização Fase 0B

**IMPLEMENTADO E TESTADO EM POSTGRESQL DESCARTÁVEL:** revisão DBA, grants mínimos,
vínculo explícito com `fazenda.cliente`, bootstrap dry-run/apply idempotente,
rollback de bootstrap conservador e harness sem rede/porta/volume. Nenhum dado real foi lido.

**DECISÃO:** `010_legacy_bootstrap_template.sql` está desabilitado; usar a função
versionada e o CLI após mapping humano. O próximo passo passa a ser Fase 0C:
homologação restaurável, definição das roles finais e desenho de uma primeira
vertical legada, ainda sem ativar produção.

Antes de implementar, ler `README.md`, decisões, autorização, migração e backlog
deste diretório, além de `docs/pasto_colheita_silos/18_CHECKPOINT...`.

## Atualização Fase 0C

**IMPLEMENTADO E TESTADO EM HOMOLOGAÇÃO ISOLADA:** harness PostgreSQL 16 exclusivo, aprovação definitiva de roles (`wins_agro_migrator`, `wins_agro_app`, `wins_agro_readonly`), validação automática de grants e restrições, backup lógico com pg_dump e restauração com pg_restore em instância descartável distinta, obtendo MATCH físico e lógico absoluto. Nenhum dado real foi utilizado.

**DECISÃO:** GO para homologação persistente da fundação (Fase 0D) e desenho de primeira operação legada somente leitura (Listagem de Fazendas Permitidas). A feature flag `ENABLE_MULTI_TENANCY_FOUNDATION` permanece desligada por padrão.

## Atualização Fase 0D

**IMPLEMENTADO E TESTADO EM STAGING PERSISTENTE:** rota `GET /api/v2/farms` com suporte completo a autenticação JWT real, autorização baseada no `ActorContext`, validação automática de memberships ativas e restrição server-side de farm access. Staging persistente isolado rodando em rede própria e API binded em `127.0.0.1:18080`.

**DECISÃO:** GO para implantação da fundação multi-tenant e ativação controlada (Fase 0E). A feature flag `ENABLE_FARMS_V2` permanece desativada por padrão em produção.

## Atualização Fase 0E1

**IMPLEMENTADO E TESTADO EM STAGING E PRODUÇÃO (READ-ONLY):** Ferramenta de inventário `inventory_readonly.py` executada de forma estritamente somente leitura via transação isolada com rollback obrigatório em produção. Geração de mappings e checklist de auditoria privados. Remediação de privacidade com remoção total de dependência de dados de auditoria, WebAuthn e sessões, reclassificando propostas para a Classe F. Relatório público sanitizado de evidências contendo apenas HMACs e contagens agregadas de recursos operacionais.

**DECISÃO:** GO para prosseguir à Fase 0E2 (Revisão Humana de Mappings). A coleta em produção está concluída e validada. A feature flag permanece desligada em produção.

## Atualização Fase 0E2

**IMPLEMENTADO E TESTADO EM AMBIENTE DE REVISÃO OFFLINE:** Criação de ferramentas offline em `scripts/fase0e2/` para validação de origem da Fase 0E1, geração de template de decisão privada e verificação de regras de conformidade. Geração do template `human_decisions_template_private.csv` sob pasta privada restrita (700/600). Todos os 94 testes validados com OK.

**DECISÃO:** GO para iniciar a revisão manual offline pelo operador humano (DECISÃO HUMANA PENDENTE / AWAITING_HUMAN_REVIEW). Nenhuma proposta foi aprovada, e a elegibilidade para a Fase 0E3 permanece zerada.
