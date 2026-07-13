#!/usr/bin/env bash
# Script de cleanup robusto e seguro para a Fase 0C
set -Eeuo pipefail

# Parâmetros esperados (ou omitidos para usar padrões limpos)
SOURCE_CONTAINER="${1:-}"
RESTORE_CONTAINER="${2:-}"
NETWORK_NAME="${3:-}"
SOURCE_VOLUME="${4:-}"
RESTORE_VOLUME="${5:-}"

echo "=== Iniciando Cleanup Controlado da Fase 0C ==="

# Remove apenas os containers específicos do teste, se informados
if [[ -n "$SOURCE_CONTAINER" ]]; then
    echo "Removendo container de origem: $SOURCE_CONTAINER"
    docker rm -f "$SOURCE_CONTAINER" >/dev/null 2>&1 || true
fi

if [[ -n "$RESTORE_CONTAINER" ]]; then
    echo "Removendo container de restauração: $RESTORE_CONTAINER"
    docker rm -f "$RESTORE_CONTAINER" >/dev/null 2>&1 || true
fi

# Remove os volumes específicos associados
if [[ -n "$SOURCE_VOLUME" ]]; then
    echo "Removendo volume de origem: $SOURCE_VOLUME"
    docker volume rm "$SOURCE_VOLUME" >/dev/null 2>&1 || true
fi

if [[ -n "$RESTORE_VOLUME" ]]; then
    echo "Removendo volume de restauração: $RESTORE_VOLUME"
    docker volume rm "$RESTORE_VOLUME" >/dev/null 2>&1 || true
fi

# Remove a rede Docker exclusiva
if [[ -n "$NETWORK_NAME" ]]; then
    echo "Removendo rede Docker exclusiva: $NETWORK_NAME"
    docker network rm "$NETWORK_NAME" >/dev/null 2>&1 || true
fi

# Remove arquivos temporários de dados sintéticos adicionais, se houver
# (Não remove o diretório de evidências em /tmp que contém relatórios sanitizados)

echo "=== Cleanup Finalizado ==="
