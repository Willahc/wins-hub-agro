# Silos e armazenagem

## Separação de domínios

**DECISÃO RECOMENDADA** — silagem e grãos têm entidades, regras, UI e ledger próprios. Uma infraestrutura comum pode oferecer localização, anexos, auditoria e inspeção, mas não uma tabela genérica com dezenas de campos nulos.

## Silo de silagem

### Capacidades

- cadastro físico e perfil;
- lotes ensilados por cultura/safra;
- volume/massa/MS útil e incerteza;
- abertura/retirada/destino;
- perdas previstas e observadas separadas;
- custo diário/animal/kg MS;
- autonomia e incompatibilidade com demanda;
- fotos, inspeções e auditoria.

Exemplo explicável:

> Silo Trincheira 01: volume estimado 1.260 m³ pelo perfil X; silagem útil 756 t na base Y; retirada 13,4 t/dia; perdas previstas 9%; autonomia 51 dias. O estoque pode terminar 17 dias antes da recuperação estimada do pasto. Revisar densidade/MS e validar o inventário.

## Silo de grãos

### Capacidades

- capacidade nominal e útil; produto/safra/lote/origem;
- entrada, saída, transferência, ajuste e quebra;
- peso corrigido, umidade, impureza, temperatura e classificação;
- secagem/aeração/inspeção e bloqueio sanitário;
- FIFO sugerido e exceção justificada;
- custos e perdas observadas/estimadas;
- inventário, histórico e exportação.

Saldo deriva do ledger por lote. Medição divergente cria reconciliação. Operação não pode deixar saldo negativo sem policy explícita e alçada.

## Mapa de unidades externas

Campos: nome, município/coordenada, distância/rota, capacidade **cadastrada**, tipo/produtos/serviços, fonte/data e contato permitido. Dados colaborativos são rotulados e aguardam validação.

Três conceitos nunca se misturam:

1. capacidade cadastrada/estática;
2. capacidade estimada;
3. capacidade disponível confirmada e válida até um horário.

SICARM/Conab sustenta o primeiro, não o terceiro. OSM pode localizar POIs, mas não comprova serviço, capacidade ou contato.

## Radar regional

Cruza PAM/produção do período com capacidade estática compatível. Exibe cobertura, déficit/superávit teórico, concentração, distância e pressão de safra. Sempre mostra ano/fonte/metodologia e aviso “não representa ocupação real”.

Para regiões/fonte com datas incompatíveis, não produzir score único; apresentar dados lado a lado ou reduzir confiança.

## Inteligência municipal

- culturas, área plantada/colhida, produção/rendimento e evolução;
- pecuária/rebanho e uso do solo;
- capacidade cadastrada e distância;
- benchmark da fazenda, usando dado informado;
- potencial comercial e oportunidade como hipótese, não fato.

## Alertas operacionais

- unidade próxima da capacidade útil;
- temperatura/umidade fora de parâmetro;
- inspeção/aeração vencida;
- saldo negativo ou divergência física;
- quebra/perda acima do limiar;
- lote antigo/FIFO não seguido;
- silagem abaixo da margem/data de término;
- capacidade regional baixa — sempre “pressão teórica”.

## Segurança e auditoria

- papel de operador registra; gestor aprova ajuste; técnico registra inspeção;
- toda transferência valida origem/destino no tenant e é atômica;
- anexo privado e export autorizado;
- lote bloqueado exige justificativa/alçada para saída;
- auditoria before/after redigida e movimento imutável;
- contato externo pode conter dado pessoal: minimização e finalidade/LGPD.

## Testes e reconciliação

- invariantes de ledger, transferência balanceada e idempotência;
- unidade/base de umidade e conservação de MS;
- concorrência de duas saídas;
- capacidade útil, ocupação e arredondamento;
- FIFO/exceção/bloqueio;
- tenant A não acessa lote/anexo/export B;
- capacidade estática nunca aparece como disponível;
- import regional é versionado e reproduzível.

## Dados externos e risco

**VALIDAÇÃO EXTERNA PENDENTE** — método automatizado, licença e atualização do SICARM/Conab. Até validação, importar snapshot controlado e exibir data; não fazer scraping. Capacidade/produção regional é inteligência de contexto, não deve contaminar o estoque privado.
