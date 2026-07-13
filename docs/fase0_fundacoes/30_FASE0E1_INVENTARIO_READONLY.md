# Inventário Somente Leitura — Fase 0E1

Este documento descreve a arquitetura e os requisitos da ferramenta de inventário somente leitura da Fase 0E1.

## 1. Objetivos
* Mapear e inventariar os clientes e recursos operacionais legados da produção.
* Identificar usuários e propostas de mapping para organizações e memberships.
* Realizar toda a operação com risco zero de alteração de dados no ambiente de produção.

## 2. Arquitetura da Ferramenta
A ferramenta foi projetada em Python (`inventory_readonly.py`) e roda acoplada ao container de execução da API, aproveitando as variáveis de conexão e pool existentes para evitar a publicação de portas ou exposição de credenciais.

### Mecanismos de Proteção e Segurança
1. **Transação Estrita de Leitura**: Cada sessão de leitura no banco inicia com comandos que configuram a transação como somente leitura:
   ```sql
   BEGIN READ ONLY;
   SET LOCAL statement_timeout = '30s';
   SET LOCAL lock_timeout = '2s';
   SET LOCAL idle_in_transaction_session_timeout = '30s';
   SET LOCAL transaction_read_only = on;
   ```
2. **Rollback Sistemático**: A transação é finalizada obrigatoriamente com um comando `ROLLBACK;`, nunca com `COMMIT`.
3. **Bloqueio de Comandos de Escrita**: Um teste estático no conjunto de testes de segurança garante que nenhuma query utilize comandos DDL/DML de escrita (`INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, `DROP`).
4. **Sem bypass local ou DSN explícito**: Toda a comunicação é feita usando a conexão interna resolvida no container, mantendo segredos protegidos.
