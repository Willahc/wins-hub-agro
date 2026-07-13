# Contrato da API GET /api/v2/farms

Este documento define formalmente a interface, os parâmetros de consulta e os formatos de resposta do endpoint de listagem de fazendas.

---

## 1. Especificação do Endpoint

* **Método**: `GET`
* **Rota**: `/api/v2/farms`
* **Autenticação**: Obrigatória via cookie `access_token`

---

## 2. Parâmetros de Consulta (Query String)

* **IMPLEMENTADO NA FASE 0D** — Validações robustas no router:

| Parâmetro | Tipo | Padrão | Regra / Limite | Descrição |
|---|---|---|---|---|
| `organization_uuid` | UUID | `None` | Opcional | Identificador público da organização (seletor). |
| `limit` | int | `25` | Min: 1, Max: 100 | Quantidade máxima de registros retornados. |
| `offset` | int | `0` | Min: 0 | Deslocamento para paginação. |
| `status` | string | `'active'` | Allowlist: `active`, `inactive`, `archived` | Filtro de status da fazenda. |

---

## 3. Resposta de Sucesso (HTTP 200)

* **CONFIRMADO NO CÓDIGO** — Campos mínimos expostos. Ausência de IDs internos sequenciais e dados de PII:

```json
{
  "organization": {
    "id": "a0000000-0000-4000-8000-0000000000a",
    "name": "Organização Sintética Alfa"
  },
  "items": [
    {
      "id": "f0000000-0000-4000-8000-000000000001",
      "name": "Fazenda Sintética Norte",
      "state": "SP",
      "municipality_code": "3550308",
      "area_ha": "150.50",
      "status": "active",
      "access_level": "manage"
    }
  ],
  "pagination": {
    "limit": 25,
    "offset": 0,
    "returned": 1,
    "has_more": false
  }
}
```

* **TESTADO UNITARIAMENTE** — O tipo do campo `area_ha` é mapeado como `str` (serialização da precisão numérica do banco de dados), impedindo distorções geradas por floats binários.
* **FORA DE ESCOPO** — Retorno de razão social sensível, endereço completo, CNPJ, ou listagem de animais.

---

## 4. Cabeçalhos HTTP Mandatórios

* **TESTADO VIA HTTP NO STAGING** — Respostas autenticadas retornam:
  - `Cache-Control: no-store, private`
  - `Pragma: no-cache`
  - `X-Content-Type-Options: nosniff`
