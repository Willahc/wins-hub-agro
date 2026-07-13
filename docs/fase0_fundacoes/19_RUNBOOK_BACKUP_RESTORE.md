# Runbook de Backup e Restauração — Fase 0C

Este guia detalha o procedimento operacional padrão para geração de backups lógicos e restauração segura da base operacional privada (`foundation`).

---

## 1. Princípios de Segurança

* **DECISÃO** — Backups de banco de dados não contêm definições globais de roles. Elas devem ser criadas separadamente no banco de destino antes de iniciar a restauração.
* **DECISÃO** — O backup não deve ser armazenado em locais do repositório Git. Deve ser gravado temporariamente e movido para armazenamento seguro.
* **CONFIRMADO NO CÓDIGO** — O script `run_homologation.sh` implementa e automatiza o processo descrito abaixo, garantindo sua reprodutibilidade.

---

## 2. Passo a Passo do Backup

O utilitário `pg_dump` deve ser utilizado com formato customizado binário, ignorando donos e permissões específicas para garantir flexibilidade ao restaurar:

```bash
pg_dump \
  -h <host_banco> \
  -U <user_admin> \
  -d <database_name> \
  --format=custom \
  --no-owner \
  --no-acl \
  > /tmp/wins_agro_fase0c_backup.dump
```

* **TESTADO EM HOMOLOGAÇÃO ISOLADA** — Parâmetros `--no-owner` e `--no-acl` evitam conflitos de propriedade de objetos e facilitam a adequação a novos ambientes.

---

## 3. Passo a Passo da Restauração

1. **Pre-criação de Roles e Tabelas Base (se aplicável)**:
   Antes do restore, crie as roles globais e conceda as devidas heranças ao administrador local:
   ```sql
   CREATE ROLE wins_agro_migrator WITH LOGIN PASSWORD '...';
   CREATE ROLE wins_agro_app WITH LOGIN PASSWORD '...';
   CREATE ROLE wins_agro_readonly WITH LOGIN PASSWORD '...';
   GRANT wins_agro_migrator, wins_agro_app, wins_agro_readonly TO CURRENT_USER;
   ```
2. **Execução do pg_restore**:
   Restaure o backup utilizando `pg_restore` sob escrutínio rígido de interrupção em erro:
   ```bash
   pg_restore \
     -h <host_restaurado> \
     -U <user_admin> \
     -d <database_name> \
     --no-owner \
     --no-acl \
     --exit-on-error \
     /tmp/wins_agro_fase0c_backup.dump
   ```
   * **TESTADO EM HOMOLOGAÇÃO ISOLADA** — `--exit-on-error` garante que qualquer falha (por exemplo, FK inválida ou tipo incompatível) aborte imediatamente a restauração.
3. **Reaplicação de Permissões (Grants)**:
   Re-aplique o script `090_foundation_grants.sql` e as permissões de schema para restabelecer o privilégio mínimo operacional de cada papel.

---

## 4. Comparação e Validação Pós-Restauração

* **IMPLEMENTADO NA FASE 0C** — Extração lógica do schema de ambos os bancos, sanitização das assinaturas do proxy de segurança (`\restrict` / `\unrestrict`), e comparação via `diff -u`.
* **IMPLEMENTADO NA FASE 0C** — Verificação lógica através de contagens de registros em todas as tabelas e conferência das constraints de chaves estrangeiras.
* **NÃO TESTADO EM PRODUÇÃO** — O processo de backup e restore foi validado apenas no harness de homologação isolada.
