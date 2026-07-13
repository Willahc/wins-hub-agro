# Evidências de Execução da Fase 0D

Este documento compila os resultados de testes automatizados, planos de execução e medições de latência coletadas no ambiente de staging.

---

## 1. Testes Automatizados (unittest)

* **TESTADO UNITARIAMENTE** — Execução da suíte completa de testes locais:
  - **Total de testes**: 73 testes executados.
  - **Resultados**: 68 testes aprovados (OK), 5 testes integrados de router ignorados (skipped) no host por ausência de FastAPI/JWT locais (conforme esperado).

---

## 2. Testes de Integração HTTP no Staging

* **TESTADO VIA HTTP NO STAGING** — Execução do script `test_http.sh` contendo 17 validações reais na porta 18080:
  - Sem Cookie: `HTTP 401 unauthenticated` (Sucesso)
  - Cookie Inválido: `HTTP 401 unauthenticated` (Sucesso)
  - Sem Membership: `HTTP 403 membership_missing` (Sucesso)
  - Membership Revogada: `HTTP 403 membership_revoked` (Sucesso)
  - Auto-resolução Owner Alfa: `HTTP 200` com 3 fazendas retornadas (Sucesso)
  - Technician Alfa: `HTTP 200` com 1 fazenda retornada (Sucesso)
  - Cross-tenant Beta tenta Alfa: `HTTP 404 resource_not_found` (Sucesso)
  - Múltiplas memberships sem UUID: `HTTP 409 organization_context_required` (Sucesso)
  - Validações de limites e paginação (limit=101, offset=-5, status=invalid): `HTTP 422` (Sucesso)
  - Verificação de headers `Cache-Control` e `Pragma` presentes (Sucesso)

---

## 3. Latência e Latency p95

* **TESTADO VIA HTTP NO STAGING** — Amostragem de 50 requisições HTTP sequenciais locais no staging:
  - **Mediana**: `6 ms`
  - **Percentil 95 (p95)**: `8 ms`
  - **Latência Limite Proposta**: < 300 ms (Aprovado com folga)

---

## 4. Plano de Consulta (EXPLAIN ANALYZE)

* **CONFIRMADO NO CÓDIGO** — Plano de execução da consulta de listagem de fazendas:
```
 Limit  (cost=112.66..112.68 rows=1 width=98) (actual time=0.279..0.280 rows=0 loops=1)
   ->  Unique  (cost=112.66..112.68 rows=1 width=98) (actual time=0.278..0.278 rows=0 loops=1)
         ->  Sort  (cost=112.66..112.66 rows=1 width=98) (actual time=0.277..0.278 rows=0 loops=1)
               Sort Key: f.name, f.public_id, f.id, f.state, f.municipality_code, ((f.area_ha)::text), a.access_level
               Sort Method: quicksort  Memory: 25kB
               ->  Merge Join  (cost=108.58..112.65 rows=1 width=98) (actual time=0.097..0.098 rows=0 loops=1)
                     Merge Cond: (f.id = a.farm_id)
                     ->  Index Scan using operational_farms_id_organization_id_key on operational_farms f  (cost=0.29..404.33 rows=100 width=64) (actual time=0.024..0.024 rows=1 loops=1)
                           Index Cond: (organization_id = 5)
                           Filter: (status = 'active'::text)
                     ->  Sort  (cost=108.30..108.30 rows=1 width=15) (actual time=0.073..0.073 rows=0 loops=1)
                           Sort Key: a.farm_id
                           Sort Method: quicksort  Memory: 25kB
                           ->  Bitmap Heap Scan on farm_access a  (cost=104.27..108.29 rows=1 width=15) (actual time=0.052..0.052 rows=0 loops=1)
                                 Recheck Cond: ((membership_id = 15) AND (status = 'active'::text))
                                 Filter: ((id IS NOT NULL) AND ((expires_at IS NULL) OR (expires_at > now())))
                                 Heap Blocks: exact=1
                                 ->  Bitmap Index Scan on farm_access_membership_status_idx  (cost=0.00..104.27 rows=1 width=0) (actual time=0.039..0.040 rows=1 loops=1)
                                       Index Cond: ((membership_id = 15) AND (status = 'active'::text))
 Planning Time: 2.622 ms
 Execution Time: 0.480 ms
```

- **Observação**: A query utiliza buscas em índices compostos (`operational_farms_id_organization_id_key` e `farm_access_membership_status_idx`), resultando em latência e uso de memória mínimos.
- **NÃO TESTADO EM PRODUÇÃO** — Nenhuma consulta de performance ou explain foi executada no banco de produção.
