# Inventário de identidade e dados

## Identidade

**CONFIRMADO NO CÓDIGO:** `app/auth.py` autentica uma identidade configurada,
assina `sub` no JWT e valida expiração. `app/main.py:96-117` aplica middleware às
APIs; TOTP e passkeys complementam o login. Não há membership persistente por
organização no estado-base.

## Dados

- **CONFIRMADO NO CÓDIGO:** `app/db.py:84-106` oferece transação reutilizável.
- **CONFIRMADO NO CÓDIGO:** `fazenda.cliente`, `animal`, `grupo_manejo` e
  movimentações formam o legado operacional (`scripts/build_fazenda_campo.sql`).
- **CONFIRMADO NO CÓDIGO:** a prospecção nacional é outra finalidade e outro
  schema. Ela não demonstra propriedade privada nem autorização operacional.
- **LACUNA:** animal/grupo/estação legados não apontam para uma fazenda operacional
  multiusuário; hoje o navegador fornece vários IDs.
- **LACUNA:** `audit()` em `app/main.py:195` é best-effort e fora da transação.

## Pontos de entrada futuros

Prioridade alta: `campo_clientes`, grupos, resumo, animais, status/cadastro,
cruzamento, estações, IATF, protocolos, venda, pesagens, sanidade, movimentações e
exportações (`app/main.py:4108-5323`). Prioridade média: ficha privada, uploads e
PDFs. Prospecção permanece sob política comercial própria.

**FORA DE ESCOPO:** nenhuma dessas rotas foi alterada nesta entrega.
