# Integração com WiNS Hub Log

## Princípio

Agro e Log têm ciclos, permissões e modelos diferentes. **DECISÃO RECOMENDADA** — contrato de API/eventos versionado; nunca consultas cruzadas diretas entre bancos como primeira opção.

## Casos de uso

- estimar viagens/frota/custo para colheita ou transferência;
- solicitar cotação/capacidade a transportadores;
- comparar rotas/armazéns/destinos;
- acompanhar status agregado de uma operação autorizada;
- identificar retorno vazio/oportunidade, com consentimento e minimização;
- incorporar restrição/risco logístico ao plano.

## Limites de contexto

Agro é dono de fazenda, plantio, produção planejada, produto/lote e janela. Log é dono de transportador, veículo, motorista, disponibilidade, rota contratada, frete e execução logística. Cada lado guarda apenas referência externa e snapshot necessário.

## Contrato candidato

### Solicitação Agro → Log

`shipment_request.v1`: event_id, organization_ref pseudonimizada, farm/site coordinates com precisão necessária, produto/classe, massa/faixa, janela, origem/destino proposto, requisitos, número estimado de viagens e contato operacional por fluxo autorizado.

### Resposta Log → Agro

`shipment_option.v1`: request_ref, opção, capacidade, número de viagens, janela, custo estimado/moeda/base, rota/duração, restrições, validade e confiança.

### Execução

`shipment_status.v1`: accepted/scheduled/in_transit/delivered/cancelled, timestamps e quantidade agregada. Não replicar telemetria detalhada por padrão.

Todos os contratos têm JSON Schema/OpenAPI, version, idempotency key, correlation ID e assinatura/autenticação de serviço.

## Padrão de integração

Transactional outbox no Agro publica evento após commit; consumidor Log deduplica `event_id`. Resposta entra por endpoint autenticado/assinado e inbox idempotente. Retry exponencial e dead-letter não bloqueiam transação agrícola. Para baixa escala, polling controlado pode preceder broker; adotar Kafka/RabbitMQ só com demanda real.

## Segurança e privacidade

- identidade de serviço rotacionável e escopos mínimos;
- tenant/consentimento/finalidade em cada solicitação;
- não expor nome, CNPJ, animais ou produção histórica desnecessários;
- coordenada pode ser aproximada até contratação;
- webhook com assinatura, timestamp e proteção de replay;
- logs sem payload sensível;
- revogação e retenção contratual;
- autorização humana antes de contratar/reservar.

## Consistência

Status do Log não altera estoque automaticamente. Entrega confirmada pode propor movimento que o Agro valida/aplica idempotentemente. Cancelamento/ajuste cria evento compensatório. Snapshots preservam preço/rota válidos no momento.

## Falhas e fallback

- Log indisponível: plano Agro continua com recursos manuais e marca cotação pendente;
- resposta vencida: não usar custo/capacidade sem revalidar;
- duplicata: inbox retorna resultado anterior;
- contrato desconhecido: quarentena e alerta;
- divergência de quantidade: reconciliação, nunca ajuste silencioso.

## Roadmap de integração

1. Descobrir APIs/modelo/identidade do Log — **VALIDAÇÃO EXTERNA PENDENTE**.
2. Publicar contrato e sandbox com dados sintéticos.
3. Estimativa somente leitura.
4. Solicitação/cotação sem contratação.
5. Status e confirmação de entrega.
6. Oportunidades/retorno vazio, após governança e consentimento.

## Critérios

- nenhum banco compartilhado;
- contrato compatível por versão e consumer-driven tests;
- reenvio não duplica solicitação/movimento;
- Log não acessa dados de outro tenant;
- indisponibilidade não impede operação local;
- custo/rota têm validade/fonte;
- contratação sempre exige ação autorizada;
- rastreabilidade ponta a ponta por correlation ID sem PII em logs.
