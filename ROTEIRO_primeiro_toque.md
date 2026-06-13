# Roteiro de 1º toque — Monte Sião (genética Nelore) · jun/13

Companion do **`icp_MASTER_montesiao.csv`**. Cada linha tem a coluna **`script`** (WA / EM / DM / TEL)
que indica qual template abaixo usar, e **`canal_recomendado`** com o canal já escolhido pela cascata.
Campos entre `{}` vêm das colunas do CSV.

## Princípios (valem pra todo canal)
1. **Personalize na 1ª linha.** Estes são seletores — a maioria já registra Nelore (`touros_nelore`). Mostre que você sabe quem eles são; nada de disparo genérico.
2. **Abra conversa, não venda.** O objetivo do 1º toque é resposta, não fechar dose. CTA leve ("faz sentido te mandar?", "posso te mostrar?").
3. **Fale de produtor pra produtor.** Monte Sião é fazenda Nelore elite (Porto Nacional-TO), não call center. Tom de colega de pecuária.
4. **Curto.** WhatsApp/DM ≤ 4 linhas. E-mail ≤ 6. Ninguém lê textão de desconhecido.
5. **Respeite o opt-out.** "Se não for do seu interesse, é só falar que não te incomodo mais." Some o contato que pedir.
6. **Horário:** WhatsApp/ligação 8h–11h ou 14h–17h, dias úteis. Evite fim de tarde/sexta à noite.

---

## WA — WhatsApp (canal `WhatsApp` / `WhatsApp/Ligacao`)
**Prioridade máxima** — é o canal que mais converte no agro. Use o nome do `operador_jovem` se houver (quem toca a fazenda no dia a dia), senão o `decisor`.

**1º toque:**
> Bom dia, {operador_jovem || decisor}! Aqui é o William, da **Monte Sião Genética** (Nelore de seleção, Porto Nacional-TO).
> Acompanho o trabalho de vocês na {fazenda} aí em {municipio}/{uf} — Nelore de qualidade.
> Tô montando um grupo seleto de criadores pra dar acesso à nossa linha de touros (mesmo padrão das centrais grandes, com preço de produtor). Posso te mandar o catálogo com DEPs e valores, sem compromisso?

**Se responder com interesse:** mandar 2-3 touros de destaque (foto + DEP + R$/dose) e abrir pra acasalamento dirigido ("me passa o perfil das suas matrizes que eu sugiro o cruzamento").

**Follow-up (se não responder em ~2 dias úteis):**
> {operador_jovem || decisor}, só pra não perder o contato — consigo te mandar aquele catálogo da Monte Sião? Se não for o momento, sem problema, me avisa. 👍

---

## EM — E-mail (canal `E-mail` / `E-mail (risco bounce)`)
Use quando `email_tier = valid`. Se `catch-all`, mande mas espere bounce — tenha WhatsApp/telefone de backup.
**Personalize o assunto com a fazenda.**

**Assunto:** Genética Nelore pra {fazenda} — catálogo + DEPs
**Alternativo:** {decisor}, touros Nelore de seleção com preço de produtor

**Corpo:**
> Olá, {decisor}, tudo bem?
>
> Sou o William, da **Monte Sião Genética**, criador de Nelore de seleção em Porto Nacional-TO.
> Vi que a {fazenda} trabalha com Nelore registrado aí em {municipio}/{uf} — por isso te escrevo.
>
> Estamos abrindo acesso à nossa linha de touros (DEPs comprovados, mesmo nível das centrais, com condição de produtor pra produtor). Posso te enviar o catálogo com as avaliações genéticas e os valores?
>
> Se fizer sentido, respondo aqui ou te mando no WhatsApp — o que for melhor pra você.
>
> Abraço,
> William — Monte Sião Genética · {seu_telefone}

---

## DM — Instagram (canal `Instagram DM`)
Maior volume do master. O perfil é da fazenda (`instagram`) — fale com quem administra a conta. Tom mais leve.

**1º toque:**
> Opa! Acompanhando o Nelore de vocês da {fazenda} aqui 👏 Sou criador também — Monte Sião Genética, em Porto Nacional-TO.
> Tô liberando acesso à nossa linha de touros pra um grupo de criadores selecionados, com preço de produtor. Posso te mandar o catálogo? Me passa um WhatsApp que fica mais fácil de te mostrar os DEPs e valores. 🐂

**Meta da DM:** migrar pro WhatsApp (pedir o número). É lá que a conversa anda.

---

## TEL — Ligação (canal `Ligacao (capturar zap)`)
Quando só tem `telefone_rfb`/`celular` e nenhum canal digital. **Objetivo nº1 da ligação: capturar o WhatsApp** do operador.

**Roteiro:**
> — Bom dia, é da {fazenda}? Aqui é o William, criador de Nelore lá de Porto Nacional, da Monte Sião.
> — Eu queria falar com **quem cuida da parte de reprodução/genética do rebanho** — costuma ser o filho/o gerente que toca isso, certo? *(pede pelo operador jovem, não o patriarca)*
> — *(com a pessoa certa)* Rapidão: a gente tá abrindo nossa linha de touros pra um grupo de criadores, com preço de produtor. Faz sentido eu te mandar o catálogo com os DEPs e valores no **WhatsApp**? Qual o melhor número?
> — *(anota o zap → daí em diante segue pelo script WA)*

**Se a pessoa certa não estiver:** "Qual o melhor horário e o WhatsApp dele que eu chamo?"

---

## Ajuste por prioridade (coluna `prioridade` / `sinal_genetico`)
- **P1 alta / P2 media** (já registram Nelore — seletores): trate como **par**, fale de DEP, mérito genético, acasalamento dirigido. Eles entendem o jogo.
- **P3 baixa / P4 sem sinal**: mais **educativo** — ganho de arroba, precocidade, padronização do rebanho. Menos jargão de seleção.
- Quem tem **`touros_nelore` alto** (ex.: Colonial 391): é cabanha forte — abordar como potencial **parceria/multiplicador**, não só comprador.

## Cadência sugerida
1º toque → follow-up em 2 dias úteis → 2º follow-up em +4 dias (canal alternativo do CSV) → encerra. Marca no CRM/planilha o status (sem resposta / interessado / não / fechou).
