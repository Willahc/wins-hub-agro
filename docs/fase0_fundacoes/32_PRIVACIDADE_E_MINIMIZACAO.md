# Privacidade e Minimização de Dados — Fase 0E1

Este documento estabelece as diretrizes de privacidade e minimização de dados aplicadas na Fase 0E1.

## 1. Diretrizes de Proteção a PII (Informações Pessoais)
Não é permitida a exposição de nomes de pessoas, nomes de fazendas reais, CPFs, CNPJs, e-mails, telefones ou coordenadas geográficas de propriedades no repositórioGit ou em logs públicos.

## 2. Pseudonimização via HMAC
Todos os identificadores legados que precisam ser compartilhados ou expostos para análise pública e relatórios são pseudonimizados usando HMAC-SHA256 alimentado por um salt dinâmico e privado gerado na execução:
* **Exemplo**: O cliente de ID `17` é transformado em `client-3fd7e68e`.
* O salt da execução é mantido em segurança e de forma exclusiva no diretório `/root/.config/wins_agro/fase0e1/`.

## 3. Remediação de Fontes de Auditoria e WebAuthn
Após revisão de privacidade, determinou-se que tabelas de WebAuthn (`prospeccao.webauthn_credential`), logs de auditoria (`prospeccao.audit_log`), sessões, cookies, tokens e logs de autenticação **não podem** ser usados como fontes de dados para mapear usuários ou memberships de forma automática.
* **Ação**: Queries a essas tabelas foram completamente removidas da allowlist. Todas as propostas derivadas de dados dessas fontes foram reclassificadas para a classe de menor confiança (Classe F).
* **Minimização Geográfica**: Os dados de Estado (UF) e Município foram completamente omitidos das tabelas públicas de evidências para evitar reidentificação cruzada.
