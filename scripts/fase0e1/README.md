# Scripts de Inventário Read-Only e Mapping — Fase 0E1

Este diretório contém as ferramentas e scripts de automação para a execução do inventário somente leitura e geração de propostas de mapping.

## Arquivos e Utilização

1. **`inventory_readonly.py`**: O script Python principal que é copiado e executado dentro do container da API. Executa em uma transação estritamente de leitura com rollback final.
2. **`run_staging_rehearsal.sh`**: Executa o ensaio de inventário no banco de staging sintético, validando que nenhuma alteração ou escrita ocorreu.
3. **`run_production_readonly.sh`**: Copia o script para o container da API de produção, executa com confirmação e recupera os resultados em `/root/.config/wins_agro/fase0e1/` sob permissões restritas.
4. **`cleanup_private_outputs.sh`**: Limpa quaisquer resíduos e arquivos temporários de `/tmp` no host ou nos containers.
