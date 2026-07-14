# Pasto Vivo — Documentação

## Descrição

Módulo de gestão de pastagens vivas para o sistema WiNS Agro. Permite o cadastro de talhões, registro de medições de forragem, controle de lotação e previsão de descanso, integrando-se ao módulo de Autonomia Alimentar para cálculos nutricionais.

## Documentos

| # | Documento | Descrição |
|---|---|---|
| 01 | [Escopo e Regras](01_ESCOPO_E_REGRAS.md) | Funcionalidades, limites, estados e fórmulas |
| 02 | [Modelo de Dados e API](02_MODELO_DADOS_E_API.md) | Schema, tabelas e endpoints |
| 03 | [Guia do Usuário](03_GUIA_USUARIO.md) | Como usar, glossário e dicas |
| 04 | [Staging, Testes e Limitações](04_STAGING_TESTES_E_LIMITACOES.md) | Ambiente de teste, testes e restrições |

## Início rápido

```bash
# 1. Staging
bash scripts/pasto_vivo/start_staging.sh

# 2. Ativar flag
# Adicione ENABLE_PASTO_VIVO=true ao docker-compose.staging.yml

# 3. Aplicar migrations
python scripts/pasto_vivo/apply_migrations.py

# 4. Testar
cd app && python3 -m unittest discover -s tests -p 'test_pasto_vivo_*.py' -v
```

## Feature Flag

| Flag | Descrição | Padrão |
|------|-----------|--------|
| `ENABLE_PASTO_VIVO` | Ativa o módulo Pasto Vivo | `false` |
| `ENABLE_PASTO_VIVO_API` | Ativa endpoints da API REST | `false` |
| `ENABLE_PASTO_VIVO_DASHBOARD` | Ativa dashboard no frontend | `false` |

## Integrações

- **Autonomia Alimentar**: Importação de dados de pastagem para cálculos nutricionais
- **Gestão de Animais**: Dados de lotação e pastejo
- **Clima e Operações**: Contexto climático no dashboard (chuva, temperatura, vento)

## Módulos Irmãos

O módulo **Silagem e Estoques** (`docs/silagem_estoques/`) é um módulo irmão que gerencia insumos armazenados (silagem, feno, concentrados). Enquanto Pasto Vivo foca em pastagens vivas (biomassa, lotação, descanso), Silagem e Estoques foca em estoques de insumos armazenados. Ambos alimentam a Autonomia Alimentar com fontes complementares de dados.