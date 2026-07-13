# Staging Persistente — Fase 0D

Este diretório contém os scripts de orquestração e validação para o ambiente de staging persistente da Fase 0D.

---

## 1. Arquitetura do Ambiente Staging

- **Projeto Docker Compose**: `wins_agro_fase0d`
- **Porta Local da API**: `127.0.0.1:18080` (não exposta na interface pública `0.0.0.0`)
- **Porta do PostgreSQL**: Não publicada
- **Rede Isolada**: `wins_agro_fase0d_backend`
- **Volume Exclusivo**: `wins_agro_fase0d_db_data`
- **Arquivo de Configuração**: `/root/.config/wins_agro/fase0d/staging.env` (gerado com permissão `chmod 600`)

---

## 2. Scripts Disponíveis

### `start_staging.sh`
Sobe o banco PostgreSQL, executa os scripts DDL de inicialização, popula com a carga sintética e sobe a API de staging.

```bash
bash scripts/fase0d/start_staging.sh
```

### `status_staging.sh`
Inspeciona os containers e a saúde do ambiente de staging.

```bash
bash scripts/fase0d/status_staging.sh
```

### `stop_staging.sh`
Para os containers do ambiente sem apagar os volumes de dados persistentes.

```bash
bash scripts/fase0d/stop_staging.sh
```

### `destroy_staging.sh`
Remove completamente containers, rede e volumes de staging. Requer a flag de confirmação `--confirm-destroy-fase0d`.

```bash
bash scripts/fase0d/destroy_staging.sh --confirm-destroy-fase0d
```

---

## 3. Scripts de Validação

- `test_http.sh`: Testa os códigos HTTP (200, 401, 403, 404, 409, 422) contra a API real.
- `test_authorization.sh`: Testa permissões e restrições por role (owner, technician, viewer, etc.).
- `test_performance.sh`: Executa testes de concorrência e mede a latência (mediana e p95).
- `validate_isolation.sh`: Garante que staging não tem acesso e nem conexões cruzadas com a produção.
