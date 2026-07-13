# Pasto Vivo

## Objetivo

Monitorar piquetes no tempo, combinando geometria, observação de campo, clima e sinal remoto para priorizar decisões. Não diagnosticar degradação automaticamente.

## Base reutilizável e lacuna

**CONFIRMADO NO CÓDIGO** — já existem Leaflet/camadas municipais (`app/frontend/mapa.html`), geometrias CAR/GeoJSONL (`scripts/pasto_full_br.py`, linhas 1–188), MapBiomas agregado e experimental por fazenda (`app/main.py`, linhas 2.754–2.817) e NDVI pontual/experimental por polígono (`app/main.py`, linhas 3.780–3.825; `scripts/ndvi_pasto_gee.py`).

**RISCO** — CAR não prova vínculo do imóvel ao usuário, geometria pode estar desatualizada e o índice atual não oferece série/qualidade por piquete. Nenhuma dessas fontes deve criar automaticamente fazenda ou piquete privado.

## Escopo proposto

- desenhar/importar limite, talhão e piquete, com área calculada e declarada;
- versionar geometria e impedir sobreposição acidental com warning;
- registrar altura, massa de forragem, cobertura, condição, foto e nota;
- calcular séries de índice, anomalia e tendência 30/60/90 dias;
- associar chuva, dias sem chuva, calor e risco de fogo;
- comparar piquetes equivalentes e registrar manejo/entrada/saída de lote;
- gerar alertas explicáveis com visita de validação.

## Pipeline remoto

1. Polígono vigente e simplificado define área de interesse.
2. Catálogo encontra cenas; filtro inicial por data/nuvem.
3. Processamento aplica máscara de nuvem/sombra, índice e estatísticas robustas.
4. Persistem percentis/mediana, pixels válidos, cenas, algoritmo e confiança.
5. Baseline respeita sazonalidade e histórico mínimo.
6. Job compara alteração e dispara sinal; não muda oferta de MS.
7. Observação de campo confirma, contradiz ou deixa inconclusivo.

Sentinel-2 atende vigor óptico; Sentinel-1 pode complementar nuvem/estrutura, mas aumenta complexidade e exige validação. **PROPOSTA** — começar apenas com Sentinel-2 e observação de campo; avaliar radar depois.

## Linguagem obrigatória

Usar “sinal”, “indício”, “estimativa”, “provável”, “análise remota” e “requer validação em campo”. Evitar “pasto degradado” sem qualificador, “doença detectada”, “capacidade real” e recomendação absoluta.

Exemplo:

> Piquete 04 — 18,6 ha. Vigor remoto 72/100; tendência 30 dias −11%; 27 mm de chuva; 81% de confiança técnica do processamento. Há sinal de cobertura irregular em 4,3 ha. Avaliar redução temporária da lotação e validar em campo.

“81%” só deve ser exibido após calibrar e definir o score; antes, usar classe baixa/média/alta com fatores.

## Clima e alertas

- chuva acumulada e dias sem chuva distinguem estação observada de grade;
- distância/altitude da estação e resolução aparecem na UI;
- risco de incêndio pode usar INPE como contexto regional;
- recuperação após chuva requer baseline local e evento de manejo;
- superpastejo é hipótese que combina pressão animal, tempo, oferta e observação — NDVI sozinho não basta.

## UX

Mapa/lista sincronizados, filtro por unidade/status/data e legenda de fonte. Detalhe mostra série, comparação, observações, lotes e alertas. Toggle separa imagem/índice/visita. Mobile captura registro e foto offline; desenho de geometria tem validação, undo e confirmação da área.

## Critérios específicos

- geometria inválida não é salva; área usa método geodésico e informa diferença declarada;
- índice guarda cenas, período, cobertura válida e algoritmo;
- baixa cobertura de pixels retorna “dados insuficientes”, não zero;
- alerta remoto contém fonte/data/confiança e ação “validar em campo”;
- observação contraditória permanece no histórico;
- troca de versão do polígono não mistura séries sem regra explícita;
- dados de outro tenant não aparecem em bbox, export, tile ou anexo.

## Validações pendentes

- espécies/sistemas e métodos de amostragem do piloto;
- baseline mínimo e limiares por região/época;
- conta, quota, licença e custo efetivo do Copernicus/openEO;
- precisão das geometrias atuais e fluxo de comprovação de vínculo;
- opção PostGIS após benchmark.
