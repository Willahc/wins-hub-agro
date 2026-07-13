# Metodologia de Classificação de Mapping — Fase 0E1

Este documento define as classes de confiança e os critérios de classificação de mapeamento legado.

## 1. Classes de Confiança (A a F)
* **Classe A — Vínculo explícito e único**: Relação direta na tabela de banco de dados (ex: e-mail do usuário correspondente a um campo `email` no registro do cliente de forma única).
* **Classe B — Vínculo explícito com pequena ambiguidade**: Relação estruturada, mas com pequenos fatores de conciliação manual pendentes.
* **Classe C — Inferência forte**: Presença de correlações indiretas fortes que exigem revisão cuidadosa.
* **Classe D — Inferência fraca**: Correlações indiretas fracas.
* **Classe E — Conflito**: Dados contraditórios de múltiplas fontes (ex: mesmo e-mail vinculado a múltiplos clientes legados distintos de maneira excludente).
* **Classe F — Sem evidência suficiente**: Casos onde a fonte original foi desconsiderada por motivos de privacidade/segurança (ex: dados originários exclusivamente de auditoria ou WebAuthn), ou ausência total de registros ligando o usuário ao cliente.

## 2. Impacto da Remediação de Privacidade
Dado que as tabelas de WebAuthn e auditoria foram removidas por restrições de privacidade, todas as propostas de usuários construídas a partir dessas fontes foram forçadas a migrar para a **Classe F**. Nenhuma proposta pode ser classificada como A ou B sem um vínculo direto estrutural permitido pelo banco legado.
