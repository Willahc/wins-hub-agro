# 04 — Staging, Testes e Limitações do Pasto Vivo

## Configuração do Ambiente de Staging

### Pré-requisitos

- Docker e Docker Compose
- Python 3.8+
- PostgreSQL 14+

### Iniciar Staging

```bash
# 1. Navegue até o diretório do projeto
cd /root/wins_agro_v1

# 2. Inicie o ambiente de staging
bash scripts/pasto_vivo/start_staging.sh

# 3. Verifique se os containers estão rodando
docker-compose -f docker-compose.staging.yml ps
```

### Aplicar Migrations

```bash
# 1. Aplique as migrations do schema pasture
python scripts/pasto_vivo/apply_migrations.py

# 2. Verifique se as tabelas foram criadas
psql -h localhost -U wins_agro_app -d wins_agro_staging -c "\dt pasture.*"
```

### Configurar Feature Flags

Edite o arquivo `docker-compose.staging.yml`:

```yaml
environment:
  - ENABLE_PASTO_VIVO=true
  - ENABLE_PASTO_VIVO_API=true
  - ENABLE_PASTO_VIVO_DASHBOARD=true
```

Ou use o arquivo `.env.staging`:

```bash
# Adicione as seguintes linhas
ENABLE_PASTO_VIVO=true
ENABLE_PASTO_VIVO_API=true
ENABLE_PASTO_VIVO_DASHBOARD=true
```

### Reiniciar Serviços

```bash
docker-compose -f docker-compose.staging.yml restart api
```

## Executando Testes

### Testes Unitários

```bash
# Execute todos os testes do Pasto Vivo
cd app && python3 -m unittest discover -s tests -p 'test_pasto_vivo_*.py' -v

# Execute um teste específico
python3 -m unittest tests.test_pasto_vivo_models -v

# Execute com cobertura
python3 -m unittest discover -s tests -p 'test_pasto_vivo_*.py' -v --with-coverage
```

### Testes de Integração

```bash
# Testes de API
python scripts/pasto_vivo/run_api_tests.py

# Testes de banco de dados
python scripts/pasto_vivo/run_db_tests.py
```

### Testes Manuais

1. **Criar talhão via API**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/pasto-vivo/paddocks \
     -H "Content-Type: application/json" \
     -d '{"name":"Teste","area_ha":5.0,"forage_type":"Brachiaria"}'
   ```

2. **Registrar medição**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/pasto-vivo/paddocks/{id}/measurements \
     -H "Content-Type: application/json" \
     -d '{"height_cm":20.0,"coverage_percent":75.0}'
   ```

3. **Iniciar pastejo**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/pasto-vivo/paddocks/{id}/grazing/start \
     -H "Content-Type: application/json" \
     -d '{"animal_count":30,"animal_type":"Bovino","average_weight_kg":400.0}'
   ```

## Limitações Conhecidas

### MVP Atual

1. **Sem sensoriamento remoto**: Não há integração com satélites ou drones
2. **Sem sensores IoT**: Coleta é 100% manual
3. **Sem previsão do tempo**: Dados meteorológicos não integrados
4. **Sem análise espacial**: Não há mapas de qualidade de pastagem
5. **Sem IA/ML**: Sem modelos preditivos ou recomendações automáticas
6. **Sem custos financeiros**: Não há rastreamento de custos de produção
7. **Sem controle de pragas**: Não há monitoramento fitossanitário

### Limitações Técnicas

1. **Performance**: Muitos talhões podem causar lentidão no dashboard
2. **Offline**: Não há suporte a工作 offline (diferente do módulo Campo)
3. **Exportação limitada**: Apenas para Autonomia Alimentar
4. **Relatórios básicos**: Sem personalização avançada de relatórios
5. **Mobile**: Interface não otimizada para dispositivos móveis

### Limitações de Negócio

1. **Valores padrão**: Fatores de conversão são genéricos (devem ser ajustados)
2. **Validação limitada**: Não valida dados com análises laboratoriais
3. **Integração única**: Apenas com Autonomia Alimentar (por enquanto)
4. **Permissões básicas**: Sem controle granular por talhão

## O que NÃO está no escopo do MVP

### Recursos Futuros Planejados

1. **Integração com satélite**: NDVI via Copernicus ou similar
2. **Sensores de altura**: Medições automáticas
3. **App mobile**: Para registro de campo offline
4. **Relatórios PDF**: Relatórios personalizados
5. **Alertas por WhatsApp/SMS**: Notificações automáticas
6. **Análise de produtividade**: Comparação com benchmarks regionais
7. **Integração com mercado**: Preços de insumos e produtos
8. **Gestão de adubação**: Recomendações de fertilização
9. **Planejamento de pastejo**: Calendário automático
10. **Multi-idioma**: Suporte a outros idiomas

### Recursos Explicitamente Excluídos

De acordo com a especificação:

- **Satélite/NDVI/Drones/GIS**: Sensoriamento remoto
- **IoT**: Sensores e dispositivos automáticos
- **IA/ML**: Inteligência artificial e machine learning
- **Previsão do tempo**: Dados meteorológicos
- **Análise espacial**: Mapas de qualidade
- **Gestão financeira**: Custos e receitas
- **Controle de pragas**: Monitoramento fitossanitário
- **Genética**: Melhoramento animal ou vegetal
- **Irrigação**: Sistemas de irrigação
- **Armazenamento**: Silos ou depósitos

## Solução de Problemas

### Erros Comuns

#### "Feature flag não encontrada"
- Verifique se `ENABLE_PASTO_VIVO=true` está no ambiente
- Reinicie o serviço após alterar variáveis de ambiente

#### "Tabela não existe"
- Execute as migrations: `python scripts/pasto_vivo/apply_migrations.py`
- Verifique se o schema `pasture` foi criado

#### "Permissão negada"
- Verifique se o usuário tem `FARM_OPERATE` ou `FARM_MANAGE`
- Confirme se a feature flag está ativa

#### "Dados não aparecem no dashboard"
- Verifique se há medições registradas
- Confirme se as datas estão corretas
- Atualize a página (Ctrl+F5)

### Logs

```bash
# Ver logs da API
docker-compose -f docker-compose.staging.yml logs api -f

# Ver logs do banco
docker-compose -f docker-compose.staging.yml logs postgres -f

# Filtrar logs do Pasto Vivo
docker-compose -f docker-compose.staging.yml logs api | grep pasto
```

### Limpar Dados de Teste

```bash
# Cuidado: isso remove todos os dados de staging
python scripts/pasto_vivo/clean_staging_data.py --confirm
```

## Ambiente de Produção

**NÃO** execute estes comandos em produção!

O módulo Pasto Vivo ainda está em fase de staging. Não deve ser utilizado em ambiente de produção até que:
1. Todos os testes estejam passando
2. A revisão de segurança seja aprovada
3. Os dados estejam validados por especialistas
4. O plano de rollback esteja documentado