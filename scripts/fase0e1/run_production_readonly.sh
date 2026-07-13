#!/usr/bin/env bash
# run_production_readonly.sh — Executa o inventário somente leitura na produção
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# 1. Valida se a flag de confirmação foi enviada
CONFIRMED=0
for arg in "$@"; do
    if [[ "$arg" == "--confirm-production-readonly" ]]; then
        CONFIRMED=1
    fi
done

if [[ "$CONFIRMED" -ne 1 ]]; then
    echo "ERRO: É necessário passar a flag --confirm-production-readonly para executar na produção." >&2
    exit 1
fi

# 2. Confirmação do Commit HEAD
expected_head="2ba8ed0e3c1fa68d1cc60c3b0f5b3f07edf5efb3"
current_head=$(git rev-parse HEAD)
if [[ "$current_head" != "$expected_head" ]]; then
    echo "ERRO: O HEAD atual ($current_head) não corresponde ao commit esperado ($expected_head)." >&2
    exit 1
fi

echo "=== Iniciando Coleta Segura na Produção ==="

# 3. Execução no Container de Produção
docker exec wins_agro_v1-api-1 mkdir -p /tmp/fase0e1/outputs
docker cp "$ROOT/scripts/fase0e1/inventory_readonly.py" wins_agro_v1-api-1:/tmp/fase0e1/inventory_readonly.py

start_time=$(date +%s)
docker exec wins_agro_v1-api-1 python /tmp/fase0e1/inventory_readonly.py --confirm-production-readonly --output-dir /tmp/fase0e1/outputs
end_time=$(date +%s)
duration=$((end_time - start_time))

# 4. Copia os resultados para o host
timestamp="$(date +%Y%m%d_%H%M%S)"
target_dir="/root/.config/wins_agro/fase0e1/${timestamp}_production"
mkdir -p "$target_dir"
docker cp wins_agro_v1-api-1:/tmp/fase0e1/outputs/. "$target_dir"

# Limpa o container
docker exec wins_agro_v1-api-1 rm -rf /tmp/fase0e1

# Ajusta permissões
chmod 700 "$target_dir"
chmod 600 "$target_dir"/*

echo "Resultados privados gerados no host em: $target_dir"
echo "Duração da coleta: ${duration} segundos."

# 5. Gera documentação sanitizada docs/fase0_fundacoes/34_EVIDENCIAS_SANITIZADAS_FASE0E1.md
python3 -c "
import json
import os

target_dir = '$target_dir'
with open(os.path.join(target_dir, 'inventory_sanitized.json'), 'r') as f:
    data = json.load(f)

duration = ${duration}

md_content = f'''# Evidências Sanitizadas da Fase 0E1

Este documento apresenta as métricas e estatísticas agregadas e sanitizadas extraídas do ambiente de produção.

> [!IMPORTANT]
> **DADO SANITIZADO** — Todos os dados pessoais, e-mails, telefones e identificadores sequenciais foram pseudonimizados usando HMAC-SHA256 com um salt privado exclusivo, ou omitidos.
> **DADO PRIVADO NÃO VERSIONADO** — Os dados reais estão armazenados em ambiente seguro fora do repositório Git.

---

## 1. Estatísticas Gerais de Produção

- **Total de Clientes (Fazendas) Inventariados**: {data['total_clients']}
- **Total de Usuários Inventariados**: {data['total_users']}
- **Duração da Coleta**: {duration} segundos.
- **Data da Execução**: {data['timestamp']}

---

## 2. Resumo de Clientes e Recursos Operacionais

| Identificador Sanitizado | Estado | Município | Animais | Grupos | Estações | Medições | Movimentações |
|---|---|---|---|---|---|---|---|
'''

for c in data['clients_summary']:
    md_content += f\"| {c['sanitized_client_id']} | {c['uf']} | {c['municipio']} | {c['animals']} | {c['groups']} | {c['stations']} | {c['medicoes']} | {c['movimentacoes']} |\\n\"

md_content += f'''
---

## 3. Registros Órfãos Detectados

- **Animais sem Cliente**: {data['orphans']['orphan_animals']}
- **Grupos sem Cliente**: {data['orphans']['orphan_groups']}
- **Estações sem Cliente**: {data['orphans']['orphan_stations']}
- **Movimentações sem Cliente**: {data['orphans']['orphan_movimentacoes']}

---

## 4. Propostas de Mapping Geradas

- **Total de Propostas**: {data['proposals_summary']['total']}

### Distribuição por Classe de Confiança

| Classe | Confiança | Descrição | Total Proposto |
|---|---|---|---|
| **A** | Altíssima | Vínculo explícito e único | {data['proposals_summary']['by_confidence'].get('A', 0)} |
| **B** | Alta | Vínculo explícito com pequena ambiguidade | {data['proposals_summary']['by_confidence'].get('B', 0)} |
| **C** | Média | Inferência forte, exige revisão humana | {data['proposals_summary']['by_confidence'].get('C', 0)} |
| **D** | Baixa | Inferência fraca | {data['proposals_summary']['by_confidence'].get('D', 0)} |
| **E** | Conflito | Conflito explícito de dados | {data['proposals_summary']['by_confidence'].get('E', 0)} |
| **F** | Insuficiente | Sem evidência suficiente | {data['proposals_summary']['by_confidence'].get('F', 0)} |

**REVISÃO HUMANA PENDENTE** — Nenhuma das propostas foi marcada como aprovada nesta fase.
'''

with open('$ROOT/docs/fase0_fundacoes/34_EVIDENCIAS_SANITIZADAS_FASE0E1.md', 'w') as f:
    f.write(md_content)
"

echo "Documento 34_EVIDENCIAS_SANITIZADAS_FASE0E1.md gerado com sucesso."
