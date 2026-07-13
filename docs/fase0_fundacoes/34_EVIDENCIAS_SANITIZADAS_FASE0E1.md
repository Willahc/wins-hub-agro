# Evidências Sanitizadas da Fase 0E1

Este documento apresenta as métricas e estatísticas agregadas e sanitizadas extraídas do ambiente de produção.

> [!IMPORTANT]
> **DADO SANITIZADO** — Todos os dados pessoais, e-mails, telefones e identificadores sequenciais foram pseudonimizados usando HMAC-SHA256 com um salt privado exclusivo, ou omitidos.
> **DADO PRIVADO NÃO VERSIONADO** — Os dados reais estão armazenados em ambiente seguro fora do repositório Git.

---

## 1. Estatísticas Gerais de Produção

- **Total de Clientes (Fazendas) Inventariados**: 1
- **Total de Usuários Inventariados**: 5
- **Duração da Coleta**: 0 segundos.
- **Data da Execução**: 20260713_165551

---

## 2. Resumo de Clientes e Recursos Operacionais

| Identificador Sanitizado | Estado | Município | Animais | Grupos | Estações | Medições | Movimentações |
|---|---|---|---|---|---|---|---|
| client-3fd7e68e | TO | Porto Nacional | 8 | 0 | 2 | 5 | 3 |

---

## 3. Registros Órfãos Detectados

- **Animais sem Cliente**: 0
- **Grupos sem Cliente**: 0
- **Estações sem Cliente**: 0
- **Movimentações sem Cliente**: 0

---

## 4. Propostas de Mapping Geradas

- **Total de Propostas**: 5

### Distribuição por Classe de Confiança

| Classe | Confiança | Descrição | Total Proposto |
|---|---|---|---|
| **A** | Altíssima | Vínculo explícito e único | 0 |
| **B** | Alta | Vínculo explícito com pequena ambiguidade | 0 |
| **C** | Média | Inferência forte, exige revisão humana | 0 |
| **D** | Baixa | Inferência fraca | 0 |
| **E** | Conflito | Conflito explícito de dados | 0 |
| **F** | Insuficiente | Sem evidência suficiente | 5 |

**REVISÃO HUMANA PENDENTE** — Nenhuma das propostas foi marcada como aprovada nesta fase.
