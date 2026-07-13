# Diretrizes de Handoff para a Fase 0E3

Este documento orienta os próximos passos e limites técnicos na transição para a Fase 0E3.

## 1. Escopo e Limites da Fase 0E3
A Fase 0E3 consiste na simulação (dry-run) das migrações e aplicações de mappings contra uma cópia restaurada e sanitizada do banco legado.

* **PROPOSTAS CLASSE F**: Propostas em classe F **não podem** seguir automaticamente para a Fase 0E3 como mappings aplicáveis.
* **Elegibilidade**: No estado atual, espera-se:
  ```text
  eligible_for_phase_0e3 = 0
  ```
* **Reclassificação futura**: Uma proposta de classe F somente poderá ser considerada candidata à Fase 0E3 em etapas futuras mediante:
  1. Apresentação de evidência operacional externa explícita;
  2. Reclassificação formal e nova decisão humana registrada em trilha de auditoria;
  3. Geração de arquivo de decisões aprovado e validado.
* **Massa de Teste Permitida**: A Fase 0E3 operará unicamente com dados de mappings sintéticos homologados ou mapeamentos manuais cadastrados do zero em etapas futuras, mantendo zero mappings reais aplicados enquanto não houver aprovação de confiança válida.
