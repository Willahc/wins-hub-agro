# Runbook: Revisão Humana de Mappings — Fase 0E2

Este runbook orienta o operador na execução do processo de revisão humana offline das propostas de mapping geradas pela Fase 0E1.

## 1. Passo 1: Validação do Pacote de Origem e Geração do Template
O operador executa o comando para validar a integridade do pacote de origem da Fase 0E1:
```bash
python3 scripts/fase0e2/validate_private_package.py \
  --source /root/.config/wins_agro/fase0e1/20260713_165551_production
```
Em seguida, gera o template de decisões humanas:
```bash
python3 scripts/fase0e2/generate_review_template.py \
  --source /root/.config/wins_agro/fase0e1/20260713_165551_production \
  --output-root /root/.config/wins_agro/fase0e2
```
Este comando criará uma subpasta com um timestamp (ex: `/root/.config/wins_agro/fase0e2/20260713_170754/`) contendo o arquivo `human_decisions_template_private.csv`.

## 2. Passo 2: Edição Manual das Decisões
O operador abre localmente o arquivo privado e preenche cada uma das cinco propostas na planilha com:
1. **decision**: Escolher unicamente entre `REJECT`, `PENDING`, `REQUEST_OPERATIONAL_EVIDENCE`, `MANUAL_REGISTRATION_FUTURE`.
2. **reason_codes**: Inserir códigos de motivos válidos (ex: `NO_EXPLICIT_RELATION`, `WAITING_HUMAN_CONTEXT`, `REQUIRE_ROLE_CONFIRMATION` ou `LEGACY_MAPPING_NOT_SAFE`).
3. **reviewer**: Nome ou identificador do revisor humano.
4. **reviewed_at**: Timestamp ISO-8601 completo com timezone (ex: `2026-07-13T17:00:00Z`).
5. **review_notes**: Observações operacionais sem informações sensíveis.
6. **human_confirmation**: Exatamente a string `I_REVIEWED_THIS_PROPOSAL`.

Salve o arquivo editado como **`human_decisions_private.csv`** no mesmo subdiretório.

## 3. Passo 3: Validação e Finalização da Revisão
Valide as decisões preenchidas:
```bash
python3 scripts/fase0e2/validate_human_decisions.py \
  --decisions /root/.config/wins_agro/fase0e2/<TIMESTAMP>/human_decisions_private.csv \
  --source /root/.config/wins_agro/fase0e1/20260713_165551_production
```
Se a validação retornar `decisions_valid=true`, finalize a revisão e gere o pacote de decisões finalizado e o relatório sanitizado:
```bash
python3 scripts/fase0e2/finalize_review.py \
  --decisions /root/.config/wins_agro/fase0e2/<TIMESTAMP>/human_decisions_private.csv \
  --source /root/.config/wins_agro/fase0e1/20260713_165551_production
```
Verifique o status do lote:
```bash
python3 scripts/fase0e2/review_mappings.py status \
  --review-root /root/.config/wins_agro/fase0e2
```
> [!IMPORTANT]
> Nunca copie e-mails legados, CPFs, nomes reais de pessoas ou chaves HMAC do salt nos chats ou documentações públicas do repositório. Toda a revisão detalhada é mantida estritamente local sob a pasta `/root/.config/wins_agro/fase0e2/`.
