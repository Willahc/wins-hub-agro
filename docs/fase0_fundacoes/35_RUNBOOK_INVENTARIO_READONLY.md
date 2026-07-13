# Runbook: Execução de Inventário Somente Leitura — Fase 0E1

Este runbook instrui sobre os passos necessários para executar a ferramenta de inventário nos ambientes de staging e produção.

## 1. Execução no Ambiente de Staging (Ensaio)
O script de staging automatiza o provisionamento e o teste negativo:
```bash
bash scripts/fase0e1/run_staging_rehearsal.sh
```
Este comando valida que tentativas de escrita são ativamente recusadas pela transação somente leitura configurada na sessão do banco.

## 2. Execução no Ambiente de Produção (Coleta Controlada)
A execução na produção exige confirmação explícita. O script copia a ferramenta para o `/tmp` do container da API, roda o inventário, extrai os resultados para `/root/.config/wins_agro/fase0e1/` e faz o cleanup automático:
```bash
bash scripts/fase0e1/run_production_readonly.sh --confirm-production-readonly
```

## 3. Validação pós-coleta
Sempre verifique a integridade dos arquivos gerados executando o checksum da coleta final:
```bash
cd /root/.config/wins_agro/fase0e1/<TIMESTAMP>_production
sha256sum -c checksums.sha256
```
Confirmar que as permissões dos arquivos privados estão restritas:
```bash
chmod 700 /root/.config/wins_agro/fase0e1/
chmod 700 /root/.config/wins_agro/fase0e1/*
chmod 600 /root/.config/wins_agro/fase0e1/*/*
```
