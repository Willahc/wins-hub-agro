# Segurança multiusuário

## Situação atual

**CONFIRMADO NO CÓDIGO** — existe autenticação forte em evolução (bcrypt/JWT, MFA opcional, passkeys, CSRF e headers), mas a identidade é uma conta configurada e o próprio código chama o app de single-tenant (`app/auth.py`, linhas 8–75; `app/main.py`, linhas 27–30 e 81–109).

**CONFIRMADO NO CÓDIGO** — endpoints recebem `cliente_id`, `animal_id`, `estacao_id`, `movimentacao_id` e consultam diretamente, sem membership/organization derivado da sessão (`app/main.py`, linhas 4.100–5.323). Autenticação global não impede IDOR entre futuros clientes.

## Modelo proposto

```text
user ─ membership(role, scope) ─ organization
                                   └ farm
                                      ├ production unit → field/paddock
                                      ├ animal lot/animals
                                      ├ silage/grain storage
                                      └ stock/operation
```

Adaptar nomes após mapear `fazenda.cliente`; não renomear/destruir dados no escuro.

## Papéis candidatos

| Papel | Permissões típicas |
|---|---|
| org_admin | membership/configuração, não segredos de sistema |
| farm_manager | operação/aprovação/exports na fazenda |
| operator | capturas/movimentos definidos, sem ajuste/aprovação |
| technician | observações, parâmetros/recomendações autorizadas |
| viewer | leitura sem mutação; export opcional separado |
| platform_admin | suporte auditado, acesso excepcional/time-bound |

Policy considera ação, recurso, organização, fazenda, papel e estado. “Admin” não substitui escopo.

## Controles obrigatórios

### Servidor

- `ActorContext` vem da sessão; tenant nunca de header/body confiado.
- IDs enviados são localizadores; repository inclui filtro tenant/farm.
- criação valida pai; atualização valida versão e ownership; export/anexo repete policy.
- resposta 404 para recurso alheio quando necessário evitar enumeração.
- FKs/constraints compostas evitam relação cruzada entre tenants.
- endpoints de lote validam cada item; limite de tamanho e sucesso parcial seguro.

### Sessão e autenticação

- usuários persistentes, convite/revogação e sessão associada a `user_id`/versão de credencial;
- cookies Secure/HttpOnly/SameSite, rotação e expiração; MFA/passa-chave conforme risco;
- logout/revogação invalida sync futuro e dispara limpeza local apropriada;
- recuperação de conta e suporte têm trilha e rate limit.

### Escrita/auditoria

- `Idempotency-Key` por organização, endpoint e conteúdo;
- auditoria na mesma transação da mutação; best-effort atual não basta para estoque;
- before/after minimizado, request/correlation ID, motivo e aprovador;
- ledger append-only e operação compensatória;
- segregação: operador propõe ajuste, gestor aprova acima de limiar.

### Arquivos e exportações

- storage privado, nomes opacos, MIME/tamanho/hash e scan quando aplicável;
- rota/url curta autorizada; sem diretório estático público;
- CSV protege formula injection; PDF `no-store` e watermark opcional;
- export registra escopo, filtros, linhas e ator; limites assíncronos.

## Offline

Cada banco local/fila é particionado por `user_id + organization_id + farm_id + device_id`. Itens contêm UUID, captured_at, entity_version, tentativas, status/erro e idempotency key. Payload sensível deve ser cifrado com chave protegida pelo sistema quando tecnicamente viável; minimizar cache.

Troca de usuário não apresenta dados anteriores. Logout online limpa chaves/dados conforme política; logout offline bloqueia acesso local e agenda revogação. Membership revogada faz servidor rejeitar sync, preservando item em quarentena para suporte, sem reatribuir a outro usuário. Conflitos são explícitos e dead-letter exportável de forma segura.

**RISCO** — o outbox atual usa `localStorage` compartilhado pela origem (`campo.html`, linhas 986–1.160). Não adicionar estoque/fotos sensíveis a ele sem particionamento e estratégia de migração.

## Ameaças e mitigação

| Ameaça | Mitigação/teste |
|---|---|
| IDOR por ID sequencial | policy/repository escopado; matriz tenant A/B em todas as rotas |
| mass assignment de owner/farm | schemas não aceitam owner efetivo; derivar do contexto |
| replay offline | unique idempotency + hash + resultado anterior |
| corrida de saldo | lock/versão/constraint e ledger transacional |
| SSRF em fonte/mapa | adapters/hosts allowlisted; sem URL do usuário |
| CSV/foto maliciosos | tamanho/MIME/schema/scan; storage não executável |
| segredo em log | redaction e allowlist de campos |
| cache vazando dados | `no-store`, SW não cacheia API, partição/limpeza local |
| export em massa | permissão específica, rate limit, auditoria e job controlado |
| suporte privilegiado | acesso time-bound, justificativa e auditoria independente |

## Dados e LGPD

Mapear finalidade/base legal, minimização, retenção, titulares e operadores antes do rollout. Coordenadas, produção, estoque, contatos e rotas podem ser comercialmente sensíveis mesmo quando não são dados pessoais. Dado público de CAR/empresa não autoriza vínculo indiscriminado a uma conta privada.

## Gate de segurança da Fase 0

- modelo de identidade/membership aprovado;
- todas as novas queries testadas com dois tenants;
- policies para read/create/update/delete/export/attachment;
- auditoria atômica e imutável;
- revogação de sessão/offline testada;
- threat model e restore de backup;
- nenhum endpoint novo aceita `organization_id` como autorização;
- logs/erros sem PII/segredo.

Sem esses gates, o MVP pode ser protótipo local, não produto multiusuário.
