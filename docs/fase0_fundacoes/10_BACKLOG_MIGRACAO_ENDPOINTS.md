# Backlog de migração de endpoints

## P0 — identidade e propriedade

- resolver cada sessão em `foundation.app_users`;
- criar UI/processo auditado de organizations/memberships/farm access;
- mapear `fazenda.cliente` para fazenda operacional sem inferência por nome/CNPJ;
- definir vínculo de animal, grupo, estação e movimentação com fazenda operacional.

## P1 — App de Campo

Migrar em slices: clientes/resumo; grupos; animais/status; medições e sanidade;
cruzamentos; estações/IATF; vendas; movimentações; exportações/PDF. Em cada slice,
substituir confiança em `cliente_id`, `animal_id`, `grupo_id` e `estacao_id` por
lookup server-side, testes 401/403/404 e auditoria.

## P2 — anexos e offline

Vincular objetos, fila e idempotency keys a usuário/organização/fazenda; proteger
download; tratar logout, troca de usuário, conflitos e fila morta.

## P3 — módulos novos

Autonomia Alimentar e estoque de silagem nascem usando a fundação. Clima, Pasto
Vivo, colheita e silos seguem o mesmo contexto.

**DECISÃO:** `/fazendas` de prospecção não entra neste backlog privado; possui
política comercial separada.
