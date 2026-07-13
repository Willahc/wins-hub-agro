# Unidades, parâmetros e fórmulas

**IMPLEMENTADO NESTA ETAPA:** `app/core/units.py` cataloga código, símbolo,
dimensão, fator, precisão e estado. Conversões usam `Decimal` e exigem a mesma
dimensão. Massa verde e matéria seca são dimensões diferentes; a passagem exige
teor explícito.

Parâmetros em `app/domain/parameters.py` guardam código, valor, unidade, origem,
fonte, escopo, versão, vigência, justificativa e confiança. Precedência:
fazenda > organização > região > global > ausência. Nenhum valor agronômico foi
criado; testes usam somente `synthetic.rate`.

Fórmulas em `app/domain/formulas.py` têm definição, versão, implementation ID,
unidades, parâmetros, premissas, fonte, checksum, revisão e confiança. Publicada
é imutável; evolução cria versão sequencial. O registry contém apenas callables
explicitamente registradas.

**DECISÃO:** valores financeiros e cálculos sensíveis usam `Decimal`; não existe
interpretador de Python nem `eval`.

**VALIDAÇÃO PENDENTE:** especialistas devem aprovar catálogo, precisão, fontes e
qualquer parâmetro técnico antes da publicação.
