# Ferramentas da Fase 0E2 — Revisão Humana Offline

Este diretório contém os scripts necessários para o fluxo offline de revisão humana das propostas da Fase 0E1.

## Scripts Disponíveis

* **`validate_private_package.py`**: Valida a integridade física, checksums e conformidade de privacidade do pacote de origem da Fase 0E1.
* **`generate_review_template.py`**: Gera o template de decisões humanas (`human_decisions_template_private.csv`) sob a pasta `/root/.config/wins_agro/fase0e2/<TIMESTAMP>/`.
* **`validate_human_decisions.py`**: Valida se as decisões e reason codes inseridos pelo operador estão em conformidade com as regras rígidas da Fase 0E2.
* **`finalize_review.py`**: Converte a revisão preenchida em um pacote privado final de decisões, gerando o relatório sanitizado público.
* **`review_mappings.py`**: Utilitário CLI para verificação de status e integração dos fluxos.
* **`cleanup_review_outputs.sh`**: Limpa arquivos temporários e backups locais de dry-run.

## Fluxo Operacional

Consulte o runbook oficial em `docs/fase0_fundacoes/39_RUNBOOK_REVISAO_PRIVADA.md` para instruções passo a passo sobre como preencher e homologar as decisões.
