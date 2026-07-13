# UX, telas e fluxos

## Navegação

Evitar quinze links novos na sidebar. **PROPOSTA** — três entradas de primeiro nível, cada uma com navegação local:

- **Pasto e Alimentação:** Visão geral, Autonomia, Piquetes/Pasto Vivo, Estoques/Silagem, Alertas.
- **Produção:** Talhões/Safra, Colheita, Recursos.
- **Armazenagem:** Silagem, Grãos, Movimentações/Inspeções, Armazéns/Radar.

Mapa continua como visão transversal. Campo recebe apenas ações operacionais essenciais. ROI Pasto Limpo permanece ferramenta e ganha links contextuais, sem virar fonte de estoque automaticamente.

## Padrão comum

Toda tela mostra fazenda/organização selecionadas, `as_of`, fonte e confiança. Cards com unidade explícita; skeleton/loading; vazio com ação concreta; erro preserva filtros e oferece retry; dado vencido não some, recebe rótulo. Mobile prioriza decisão/ação, tabelas viram cards ou scroll identificado. Teclado, foco, contraste, labels e mensagens não dependem apenas de cor.

## Telas

### Visão geral Pasto e Alimentação

- **Usuários:** gestor, técnico e leitura.
- **Filtros:** fazenda, unidade, período, cenário.
- **Cards:** demanda MS/dia, oferta/dia, déficit/superávit, estoque MS, autonomia, data de ruptura/confiança.
- **Gráficos:** curva de saldo e composição de oferta; tabela de lotes/estoques.
- **Alertas/ações:** revisar parâmetros, criar cenário, registrar estoque, exportar PDF.
- **Vazio:** checklist rebanho → consumo → pasto → estoque.
- **Offline:** último snapshot rotulado; cálculo novo somente se todos os insumos locais/versionados estiverem presentes.

### Autonomia alimentar

Wizard auditável: escopo → rebanho → pasto → estoques → perdas/parâmetros → revisão → resultado. Cada parâmetro mostra valor, unidade, origem e “alterar neste cenário”. Resultado explica equação e intervalo. Ação “aplicar cenário” cria operações propostas, nunca movimentos automáticos.

### Piquetes/Pasto Vivo

Mapa com desenho/edição autorizada, lista sincronizada, área, último campo/satélite, vigor/tendência/confiança. Detalhe: série 30/60/90, chuva, observações/fotos e alertas. Estados “sem polígono”, “nuvem/dado insuficiente”, “geometria inválida”. Mobile captura ponto/foto/altura; edição complexa de polígono pode exigir desktop.

### Estoques e silagem

Cards por alimento/local, ledger recente e reconciliação. Silo detalha perfil, lote, MS, perdas, retiradas, lotes atendidos, autonomia e custo. Ações offline: retirada, medição, inspeção. Divergência pede ajuste com motivo, não edição de saldo.

### Alertas

Fila por severidade/entidade, filtros e agrupamento. Cada alerta mostra valor/limite, fonte/data, confiança, por que disparou, recomendação, próxima avaliação. Ações: abrir entidade, criar cenário, reconhecer, descartar com motivo. Técnico pode registrar validação de campo.

### Talhões e safra

Mapa/lista; cultura, cultivar, datas, finalidade, área, produtividade esperada e estágio. Relação com ZARC é contextual por safra e município, não bloqueio automático. Vazio guia cadastro de talhão/safra.

### Janela de colheita

Inputs de cultura/plantio/maturidade, clima, máquinas, veículos, recebimento/silo. Timeline por dia com faixa de produção, horas, viagens, chuva/solo/risco e recurso limitante. Cenários comparáveis; recalcular quando previsão muda, mostrando horário do run.

### Silos de grãos

Resumo capacidade útil/ocupação/livre, lotes e qualidade. Detalhe com ledger, FIFO sugerido, temperatura/umidade, inspeções, aeração/secagem, perda estimada e custo. Bloqueio sanitário/qualidade sobrepõe FIFO com justificativa.

### Armazéns próximos e radar

Mapa/lista com distância aproximada/rota, serviço, capacidade **cadastrada**, fonte/data. Filtro produto/distância/serviço. Disponibilidade aparece apenas “confirmada em …, válida até …”. Radar municipal apresenta produção, capacidade, cobertura e déficit **teórico**, com anos compatíveis e metodologia.

### Inteligência municipal

Culturas, área, produção, produtividade, pecuária, armazenagem e comparação regional. Comparação da fazenda usa dado informado e label de benchmark; não prova produção.

## Fluxos críticos

### Primeiro balanço

Selecionar fazenda → revisar animais/lotes → informar peso/consumo faltante → medir/estimar pasto → registrar silagem/feno/suplemento → revisar unidades/perdas → executar → salvar snapshot → criar cenário/alerta.

### Retirada offline

Abrir silo previamente sincronizado → informar massa/medida e lote destino → app mostra conversão/MS e fonte → salvar UUID local → sincronizar → servidor valida membership/silo/lote/versão → aceita/duplica/conflita → atualizar saldo.

### Alerta remoto

Job detecta sinal → regra gera alerta com confiança → técnico abre série → visita/captura observação → confirma/descarta com motivo → recomendação e confiança são reavaliadas. Nenhuma mudança automática de lotação.

## Permissões na UX

Ocultar ação ajuda, mas servidor é autoridade. Leitura vê dados/export permitidos; operador registra movimentos/observações; técnico valida parâmetros/recomendações; gestor aprova cenários/ajustes; admin gerencia membership. Export e anexos exigem a mesma policy do recurso.

## Integrações atuais

- `base.html` fornece shell e ativo (`app/frontend/base.html`, linhas 1–103).
- Mapa/Leaflet fornece padrão inicial, mas estilos/JS devem ser componentes escopados (`app/frontend/mapa.html`).
- Campo fornece interação compacta/outbox (`campo.html`), a ser endurecida para multiusuário.
- PDF gera snapshot; incluir fontes/fórmulas/confiança.
- ROI Pasto Limpo pode prepopular cenário somente mediante revisão e confirmação, mantendo fórmulas próprias intactas.
