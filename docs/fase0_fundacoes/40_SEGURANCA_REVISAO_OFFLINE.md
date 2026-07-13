# Segurança da Revisão Offline — Fase 0E2

Este documento estabelece as restrições e controles de segurança cibernética aplicados nas ferramentas de revisão da Fase 0E2.

## 1. Isolamento de Rede e Banco de Dados
A ferramenta da Fase 0E2 é estritamente offline:
* **NENHUM MAPPING APLICADO**: Os scripts não possuem dependência de `psycopg`, `asyncpg`, `sqlalchemy` ou conexões TCP/IP de banco.
* **Isolamento de API**: Não há chamadas HTTP, requisições com `requests`, `httpx` ou `urllib`.
* **Sem Docker/Git**: Chamadas subprocess para comandar containers, kubectl ou git são ativamente rejeitadas no código.

## 2. Mitigação contra Path Traversal e Injeções
* **Path Traversal**: Todos os caminhos de arquivos são resolvidos via `os.path.realpath` e seu prefixo validado contra `/root/.config/wins_agro/` e `/tmp/`. Caminhos apontando para fora dessas áreas são rejeitados com `SystemExit(2)`.
* **Simlinks**: Abertura de links simbólicos é bloqueada com `os.path.islink` para prevenir sequestros de arquivos sensíveis.
* **HTML/URL injection**: Campos textuais livres (como `review_notes`) rejeitam tags HTML `<` e `>` e prefixos de URL `http` ou `https`.
* **Escrita Atômica**: A escrita dos pacotes de decisões e resumos é feita gerando arquivos temporários (`.tmp`), aplicando `fsync`, fechando-os, renomeando-os (`os.rename`) e restringindo suas permissões de acesso com `chmod 600` e `700` para diretórios.
