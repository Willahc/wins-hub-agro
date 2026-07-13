# Runbook de Staging Persistente — Fase 0D

Este runbook orienta os operadores e revisores na gerência do ambiente de staging isolado da Fase 0D.

---

## 1. Localização e Arquivos

* **IMPLEMENTADO NA FASE 0D** — O ambiente reside em `scripts/fase0d/`:
  - `docker-compose.staging.yml`: Configuração dos containers staging_db e staging_api.
  - `/root/.config/wins_agro/fase0d/staging.env`: Arquivo de variáveis de ambiente sintéticas (gerado com permissões `600`).

---

## 2. Inicialização do Ambiente

1. Certifique-se de que o arquivo `/root/.config/wins_agro/fase0d/staging.env` existe com credenciais sintéticas.
2. Execute o start script:
   ```bash
   bash scripts/fase0d/start_staging.sh
   ```
   * **TESTADO VIA HTTP NO STAGING** — Este script realiza o build da API staging (`wins_agro_fase0d_api:staging`), sobe os containers, aguarda o Postgres, aplica migrações DDL e seeds sintéticos de forma idempotente, e valida o healthcheck da API em `http://127.0.0.1:18080`.

---

## 3. Monitoramento e Diagnóstico

* Para inspecionar os containers e logs sem exibir senhas ou DSNs:
  ```bash
  bash scripts/fase0d/status_staging.sh
  ```

---

## 4. Finalização e Teardown

### Pausa Segura (Sem Perda de Dados)
Para suspender a execução dos containers mantendo o banco de dados persistente no volume Docker:
```bash
bash scripts/fase0d/stop_staging.sh
```

### Destruição Completa (Tear Down)
Para apagar todos os recursos de staging (containers, rede, volumes e opcionalmente arquivo env):
```bash
bash scripts/fase0d/destroy_staging.sh --confirm-destroy-fase0d
```
* **DECISÃO** — A remoção exige confirmação explícita de flag para evitar acidentes com os containers de produção no mesmo host.
* **NÃO TESTADO EM PRODUÇÃO** — Nenhuma das rotinas descritas deve ser executada apontando para credenciais ou portas de produção.
