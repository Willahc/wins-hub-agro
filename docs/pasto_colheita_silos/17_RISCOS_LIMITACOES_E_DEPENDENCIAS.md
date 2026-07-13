# Riscos, limitações e dependências

## Registro de riscos

| Risco | Prob./impacto | Sinal | Mitigação/gate | Responsável candidato |
|---|---|---|---|---|
| IDOR/single-tenant | alta/crítico | acesso por trocar ID | Fase 0, policy/repository, testes A/B | engenharia/segurança |
| Semântica cliente=fazenda | alta/alto | dados duplicados/escopo errado | mapping e domínio aprovado antes de migration | produto/dados |
| Unidade/MS incorreta | alta/crítico | saldos/custos implausíveis | catálogo unidade, base explícita, golden cases | zootecnia/engenharia |
| Parâmetro universal | alta/alto | recomendação inadequada | versão/escopo/fonte/aprovação | especialista |
| Satélite como diagnóstico | média/alto | alertas falsos/linguagem absoluta | confiança, campo, disclaimer, calibração | agronomia/produto |
| Fonte externa instável | alta/médio-alto | atraso/schema/429 | adapters, cache/freshness/circuit/fallback | dados/SRE |
| Licença/redistribuição | média/crítico | ausência de termo por dataset | revisão jurídica/registro; feature off | jurídico/produto |
| VPS sem capacidade | média/alto | swap/disco/latência | medir budget; worker/recorte/remoto | SRE |
| Outbox localStorage | alta/alto | vazamento/quota/fila misturada | IndexedDB particionado/minimização/revogação | frontend/segurança |
| Ledger concorrente | média/crítico | saldo negativo/duplicado | transação/lock/version/idempotência | backend |
| Cadastro = disponibilidade | alta/alto | promessa comercial falsa | labels/modelos separados, fonte/data | produto/dados |
| Forecast desatualizado | alta/alto sazonal | plano usa run antigo | issued_at/freshness/recalcular | clima/operação |
| Custo/benchmark enganoso | média/alto | decisão financeira indevida | premissas/cenários/faixas/disclaimer | financeiro/produto |
| Acoplamento Agro–Log | média/alto | falha em cascata/migração difícil | contrato/outbox/inbox, sem DB comum | arquitetos |
| Anexo/foto sensível | média/alto | URL pública/metadata | storage privado/auth/retention | segurança |
| Monólito crescente | alta/médio | conflitos/cobertura baixa | novos domínios modulares; sem big bang | engenharia |
| Auditoria best-effort | alta/alto | movimento sem trilha | auditoria transacional nos módulos novos | backend/compliance |

## Limitações confirmadas

- autenticação atual é single-user/single-tenant;
- SQL de negócio está concentrado no monólito e não há repository/policy por tenant;
- service worker só torna shell/vendors disponíveis; API privada não é offline;
- outbox usa localStorage;
- MapBiomas/NDVI atuais são agregados/experimentais, não série validada de piquete;
- não há clima, estoque, silo, safra, job runner ou alert engine de domínio confirmados;
- Cliente Inteligente é produto separado; padrões podem inspirar, dados/modelos não devem ser misturados;
- não foram medidos recursos livres da VPS nem consultado o banco.

## Dependências humanas

- especialista zootécnico: consumo, categorias, perdas, margem e autonomia;
- agrônomo/forragicultor: massa/utilização, manejo, satélite e confiança;
- especialista em silagem/grãos: densidade/MS, perfil, umidade, secagem, aeração e quebra;
- operador de campo: fluxo/medição/offline;
- jurídico/LGPD/licenças: fontes, geodados, contatos, retenção e integração;
- WiNS Hub Log: contrato, identidade, sandbox e governança;
- SRE/DBA: capacity, PostGIS, backups, worker e observabilidade.

## Dependências técnicas

- ambiente de teste PostgreSQL e dados sintéticos;
- identidade persistente/membership/policies;
- catálogo de unidade/fonte/fórmula;
- storage privado de anexos;
- scheduler/worker isolado;
- decisão PostGIS após spike;
- contas/tokens autorizados para Copernicus/ANA e possivelmente outras fontes;
- documentação/API do Log.

## Validações externas pendentes

- INMET: API estável, limites, licença/redistribuição e acesso operacional;
- ZARC: recurso/dataset vigente, API/automação e licença;
- Conab/SICARM: extração em lote, licença, frequência e campos;
- MapBiomas: termos de cada coleção/produto, armazenamento/uso comercial e método;
- Embrapa GeoInfo: dataset específico, licença e estabilidade;
- Copernicus: quota/custo/licença do fluxo escolhido;
- CAR/SICAR: termos, qualidade e processo legítimo de vínculo à fazenda;
- roteamento/logística: motor/provedor/licença/custo;
- fontes estaduais/municipais: caso a caso.

## Segredos versionados — observação sem conteúdo

Durante o inventário por nomes de arquivos, foram observados caminhos que merecem auditoria separada, sem abrir ou reproduzir valores: `.env`, `.backup_env`, `scripts/.env.gcp`, `ci-data/admin_token.txt`, `nginx/.htpasswd_prospec` e `MFA_TOTP_SECRET.recovery.asc` (linhas não inspecionadas). Alguns podem ser deliberadamente não versionados/criptografados.

**RISCO** — confirmar com `git ls-files --error-unmatch <caminho>` e política de segredos em tarefa específica, sem imprimir conteúdo. Esta missão não alterou esses arquivos.

## Decisões abertas

1. organização versus grupo econômico e cardinalidade cliente/fazenda;
2. papel de técnico entre organizações;
3. método de cálculo e vigência dos parâmetros do MVP;
4. PostGIS versus GeoJSON no piloto;
5. IndexedDB/cifragem e política de logout offline;
6. fonte climática primária por região;
7. processamento Copernicus/openEO e budget;
8. método de custeio/FIFO e regras regulatórias;
9. contrato de disponibilidade do armazém;
10. contrato e titularidade com Log.

## No-go conditions

- implementar módulo privado antes de policy multi-tenant;
- lançar autonomia sem unidade/snapshot/fórmula versionada;
- ativar fonte sem termos/metadados/fallback;
- usar dado remoto para decisão irreversível automática;
- processar raster massivo na VPS sem capacity test;
- expor capacidade cadastrada como vaga;
- sincronizar offline sem validação de membership e idempotência;
- acoplar bancos Agro/Log para acelerar o MVP.
