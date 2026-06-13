# WiNS Hub Agro — Dossiê da Plataforma
### Documento de referência para apresentação a clientes e investidores
**Versão:** Junho/2026 · **Domínio:** winshubagro.cloud · **Uso:** material de venda / análise de prospects

> Este documento descreve a plataforma como ela está **hoje, em produção**. Onde há distinção entre
> "dado de demonstração" e "dado de cliente", ela está marcada — para você vender sem se expor.

---

## 1. Resumo executivo

O **WiNS Hub Agro** é uma plataforma de **inteligência genética e comercial para pecuária de elite**.
Ela une, num só lugar, três coisas que hoje vivem soltas no mercado: o **catálogo genético** dos
reprodutores (touros e matrizes com suas avaliações/DEPs), a **ferramenta de acasalamento** que prevê o
resultado do cruzamento antes de ele acontecer, e a **gestão de rebanho em campo** pelo celular — tudo
amarrado por um motor que **aprende com cada cruzamento realizado**.

Em uma frase de venda: *"é o sistema que transforma a genética que você vende em previsão de resultado
na tela do cliente — e melhora sozinho a cada bezerro que nasce."*

Vende-se para **cabanhas e centrais de genética** (que usam como ferramenta de venda + gestão),
tendo o **veterinário/zootecnista** como canal e o **produtor** como beneficiário final.

---

## 2. O problema que resolve

A decisão genética na pecuária brasileira ainda é feita no "olho" e no relacionamento. O criador que vende
sêmen não tem como **mostrar ao cliente, na hora, o que aquele touro produz na vaca dele**. O produtor
compra dose sem ver projeção de retorno. E ninguém fecha o ciclo: o que foi *previsto* no acasalamento
quase nunca é comparado com o que de fato *aconteceu* (prenhez, peso do bezerro).

O WiNS Hub Agro ataca exatamente esse vão:

| Dor do mercado | O que a plataforma faz |
|---|---|
| "Não consigo provar o valor do meu touro na hora da venda" | Resultado do cruzamento na tela + PDF em segundos |
| "O produtor não enxerga retorno financeiro" | Proposta de retorno (R$/cria, ROI, prenhez estimada) |
| "Minha gestão de rebanho é caderno/planilha" | App de campo offline-first (pesagem, sanitário, IATF, agenda) |
| "Não sei se minha recomendação genética funcionou" | Flywheel: previsto × realizado, o motor recalibra sozinho |
| "Não sei para quem prospectar" | Base de leads + mapa de oportunidade (desertos veterinários) |

---

## 3. Como funciona — as três superfícies

### 3.1 Hub Web (desktop) — o cérebro
Painel completo para o dono da genética e sua equipe comercial:
- **Catálogo genético** — touros e matrizes com DEPs, IQGg, preço de dose, por raça/central/UF.
- **Acasalamento dirigido** — escolhe a matriz, o motor ranqueia os touros (mérito + complementaridade +
  consanguinidade + preço) e prevê o bezerro.
- **Cruzamento livre** — cruza qualquer touro × qualquer vaca, com bloqueio automático de parentesco.
- **Marketplace & Mapa** — demanda por região, rebanho por município, camadas de leite/valor/rebanho.
- **Aprendizado (flywheel)** — previsto × realizado por touro, calibração da taxa de prenhez.
- **Prospecção** — fila de leads (decisor + contato) e relatórios territoriais em PDF.

### 3.2 App de Campo (celular/PWA + APK Android) — as mãos
Aplicativo **offline-first** que funciona sem sinal no curral e sincroniza depois:
- Cadastro de animais (com OCR do brinco por foto), pesagem, escore, eventos sanitários.
- **Agenda sanitária** com alertas (vacina vencendo, protocolo).
- **Estação de monta / IATF em lote** — insemina o lote inteiro num toque, gera a agenda do protocolo.
- **Diagnóstico de gestação (DG)** — confirma prenhe/vazia → é o que alimenta o aprendizado.
- **Cruzar do catálogo** — escolhe touro × vaca, **vê o bezerro previsto na tela na frente do cliente**
  (IQGg, ganho R$/cria, prenhez) e só então emite o **Parecer** ou a **Proposta de retorno** em PDF para
  enviar no WhatsApp.

### 3.3 Simulador público — a isca comercial
Página aberta (sem login, zero dados sensíveis) que o vendedor abre na fazenda: o produtor vê quanto ganha
usando um touro do catálogo nas matrizes dele. Gera o PDF da proposta na hora.

---

## 4. O que entrega de resultado

**Para a cabanha / central de genética (cliente que paga):**
- Fecha mais venda de sêmen/embrião mostrando resultado e retorno na hora, com documento profissional.
- Vira o "sistema operacional" da estação de monta (IATF, protocolo, agenda, DG).
- Constrói um **histórico de performance dos próprios animais** que nenhum concorrente tem.

**Para o veterinário/zootecnista (canal):**
- Ferramenta técnica que dá autoridade na recomendação e amarra o relacionamento com o produtor.

**Para o produtor (beneficiário):**
- Decisão de cruzamento com base em previsão, não em achismo; projeção de retorno antes de comprar.

**Resultado mensurável que a plataforma rastreia:** taxa de prenhez prevista × realizada por touro,
ganho de peso à desmama dos filhos, evolução do IQGg do rebanho ao longo das safras.

---

## 5. Ativos de dados (o que já está no banco)

Estes são números **reais, em produção hoje**:

| Ativo | Volume |
|---|---:|
| Reprodutores (touros) catalogados | **59.119** |
| Matrizes (fêmeas) | **45.650** |
| Avaliações genéticas (DEPs/índices) | **985.323** |
| Raças com avaliação genética | **18** |
| Características genéticas mapeadas | **55** |
| Centrais de inseminação | **19** |
| Ofertas comerciais (com preço de dose) | **1.276** |
| Municípios mapeados (cobertura/rebanho) | **5.536** |
| **Rebanho bovino mapeado** | **~238,6 milhões de cabeças** |
| "Desertos veterinários" identificados | **1.879 municípios** |
| Estabelecimentos rurais (base de leads) | **359.603** |
| Sócios/decisores vinculados | **188.838** |

**Cobertura por raça (touros com avaliação):** Nelore 47.848 · Limousin 5.181 · Brahman 1.218 ·
Brangus 756 · Guzerá 651 · Santa Gertrudis 485 · Caracu 447 · Sindi 351 · Canchim 258 · Braford 198 ·
Girolando 195 · Montana 194 · Senepol 191 · Wagyu 169 · Hereford 118 · Tabapuã 116 · Angus 80 ·
Gir Leiteiro 73. Corte e leite cobertos.

**Fontes da genética:** Geneplus (sumários públicos), CRV, Conexão Delta G (Hereford/Braford),
Embrapa (Girolando e Gir Leiteiro), ABCBRW (Wagyu), PROMEBO (Angus) — agregadas e normalizadas por raça.

> **Transparência importante para a venda:** todo o acervo genético acima é **base de demonstração**,
> montada a partir de **fontes públicas**, para *provar* o produto funcionando. Ele **não é** um dado
> proprietário secreto — qualquer um, com trabalho, chega a fontes parecidas. O **valor proprietário e
> não-copiável** nasce quando um cliente entra: o **resultado real dos cruzamentos** que a plataforma
> gerencia (ver seção 8). Venda a plataforma pela capacidade e pelo fosso que ela constrói, não pelo
> catálogo público.

A base de **leads comerciais** (Receita Federal/CNPJ) é real e útil, com uma ressalva honesta: o universo
formalizado como CNPJ é concentrado em SP; na fronteira (MT/MS/GO/PA) o pecuarista opera como Produtor
Rural Pessoa Física (CPF) e não aparece no CNPJ. A prospecção combina CNPJ + enriquecimento de contato
do decisor (sócio, telefone, WhatsApp, Instagram).

---

## 6. Arquitetura e infraestrutura (VPS)

Stack enxuta, barata de operar e fácil de escalar:

- **Servidor:** VPS Linux (KVM), **2 vCPU / 8 GB RAM / 96 GB de disco** (17% usado hoje — folga grande).
- **Aplicação:** API em **Python/FastAPI**, banco **PostgreSQL 16**, proxy **Nginx**, tudo em **Docker**.
- **Banco de dados:** ~1 milhão de avaliações genéticas + base de leads, organizado em schemas
  (catálogo, mercado, fazenda, prospecção, CNPJ). Backup automático diário **com cópia em segundo
  servidor** (offsite) — se um cair, o outro tem o dado.
- **Frontend:** PWA instalável + **APK Android** (app de campo roda como aplicativo nativo).
- **Domínio com HTTPS** (certificado Let's Encrypt, renovação automática).
- **Custo de operação:** ordem de **dezenas de reais/mês** de VPS — a margem do produto é altíssima.

A arquitetura comporta o crescimento do número de fazendas/usuários sem reescrita; o gargalo de escala não
é técnico, é comercial (quantos clientes).

---

## 7. Segurança e conformidade

A plataforma passou por **auditoria de segurança completa** (junho/2026) e está endurecida:

- **Acesso:** login com senha criptografada (bcrypt), sessão por token assinado (JWT), todas as rotas de
  dados exigem autenticação.
- **Rede:** firewall ativo (só portas 80/443/22), banco de dados acessível **só internamente** (nunca
  exposto à internet), proteção anti-força-bruta (fail2ban + rate-limit), SSH só por chave.
- **Banco:** a aplicação conecta com um usuário de **privilégio mínimo** (não é administrador do banco);
  o container roda como usuário **não-root**.
- **Dados (LGPD):** PII (dados de leads) com controle de acesso e **trilha de auditoria** em exportações;
  conteúdo sensível fora do código-fonte; segredos rotacionados e removidos do histórico.
- **Continuidade:** backup diário automático + offsite, certificado HTTPS auto-renovável, containers que
  voltam sozinhos após reinício.
- **Resiliência de campo:** o app **não perde dado** mesmo sem sinal — captura offline, fila persistente,
  reenvio idempotente (não duplica) quando a conexão volta.

Resumo para o cliente: *"seu dado de rebanho é insubstituível, e a plataforma trata ele como tal —
backup duplo, acesso controlado e nada que se perca no curral sem sinal."*

---

## 8. O diferencial — o fosso competitivo (flywheel)

Ferramenta que **recomenda** genética, qualquer um copia (o dado é público). O que **não se copia** é o
**resultado real** dos cruzamentos que a plataforma gerencia. O WiNS Hub Agro foi desenhado como um
**sistema que aprende**:

```
Estação de monta (IATF em lote)  →  cruzamentos com PREVISÃO registrada
        ↓
Diagnóstico de gestação (prenhe/vazia)  →  captura o REALIZADO de prenhez
        ↓
Nascimento + pesagem do bezerro  →  captura o REALIZADO de ganho
        ↓
Aprendizado: previsto × realizado  →  o motor RECALIBRA sozinho
        ↑__________________________________________________________|
```

Cada cliente que usa a plataforma **alimenta o motor** com dados que ninguém mais tem. Quanto mais fazendas,
mais preciso o motor fica, mais difícil de competir — é um **efeito de rede de dados**. Esse é o argumento
de **investidor**: não é um software de gestão a mais, é um ativo de dados que se valoriza com o uso.

---

## 9. Estágio atual e roadmap (honesto)

**Onde está hoje:**
- Plataforma **completa e em produção** (Hub + App + Simulador + flywheel), estável, segura e testada.
- **Pré-primeiro-cliente:** roda sobre base de demonstração; o alvo de primeiro cliente é uma cabanha
  Nelore de elite (negociação em andamento). Hoje é **mono-cliente** por design.

**Próximos passos por fase:**
- **Multi-cliente (multi-tenant):** isolar dados por fazenda — gatilho é a entrada da 2ª fazenda. (Trabalho
  pequeno, já mapeado.)
- **Ingestão de rebanho real do cliente** (genômica própria das vacas) — destrava a recomendação 100% real.
- **App nativo avançado** (offline em SQLite, GPS, balança/bastão Bluetooth) — depende de uso de campo real.
- **Calibração automática do motor** — já parcialmente no ar; amadurece com dados acumulados.

> Mensagem de venda honesta: *"a plataforma está pronta e provada; o que falta é dado do seu rebanho —
> e é exatamente o seu dado que constrói a vantagem que ninguém vai te tirar."*

---

## 10. Perfil de cliente ideal (ICP) — para analisar prospects

**Cliente que PAGA (licencia a plataforma):**
- Cabanha / haras genético ou central de inseminação que **vende sêmen, embrião ou animais de elite**.
- Tem catálogo próprio de reprodutores e equipe comercial (ou vende direto).
- Opera estação de monta / IATF (gera volume de cruzamentos = combustível do flywheel).
- Perfil-âncora: criador Nelore de elite, dose na faixa de centenas de reais, margem alta, marca a zelar.

**Canal (multiplicador):** veterinários e zootecnistas que atendem várias fazendas — um técnico leva a
plataforma a dezenas de produtores.

**Como qualificar um prospect (perguntas-chave):**
1. Vende genética (sêmen/embrião/animal) ou só produz boi gordo? → *o primeiro é cliente, o segundo é
   beneficiário.*
2. Tem estação de monta / faz IATF em lote? → *quanto mais cruzamentos, mais valor.*
3. Quem decide a genética — o dono, o veterinário, o gerente? → *defina o decisor antes de abordar.*
4. Como mostra resultado ao comprador hoje? → *se é "no papo", a plataforma é um salto.*

---

## 11. Modelo comercial sugerido

A recomendação (a refinar por negociação) é **licença + royalty**, não venda de software avulso:
- **Licença/assinatura** pela plataforma (Hub + App + Simulador).
- **Royalty / participação** sobre o que a plataforma ajuda a vender (doses, embriões) — alinha o ganho da
  WiNS ao sucesso do cliente.
- Tese **"motor + combustível":** a plataforma é o motor; o catálogo e o rebanho do cliente são o
  combustível. Vende-se o motor e cobra-se pelo uso.

O custo de operação é baixíssimo (VPS de dezenas de reais/mês), então a margem é dominada pelo modelo
comercial, não pela infraestrutura.

---

## 12. Ficha técnica resumida (para anexo)

| Item | Detalhe |
|---|---|
| Produto | Plataforma de inteligência genética + gestão de rebanho + prospecção |
| Superfícies | Hub Web · App de Campo (PWA + APK Android) · Simulador público |
| Stack | Python/FastAPI · PostgreSQL 16 · Nginx · Docker · Linux |
| Infra | VPS 2 vCPU / 8 GB RAM / 96 GB · HTTPS · backup diário + offsite |
| Base genética | 59.119 touros · 45.650 matrizes · 985 mil avaliações · 18 raças |
| Base comercial | 359.603 estabelecimentos · 188.838 decisores · 5.536 municípios |
| Rebanho mapeado | ~238,6 milhões de cabeças |
| Segurança | Auditada (jun/2026): bcrypt/JWT, firewall, least-privilege, LGPD, backup duplo |
| Diferencial | Flywheel previsto × realizado — ativo de dados que se valoriza com o uso |
| Estágio | Em produção, provada, pré-primeiro-cliente (mono-cliente hoje) |

---

*Documento gerado em junho/2026. Os números de base de dados refletem o estado de produção na data.
A base genética é demonstrativa (fontes públicas); o valor proprietário nasce com o dado de cada cliente.*
