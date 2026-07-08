#!/bin/sh
set -e

if [ -n "${LITESTREAM_REPLICA_BUCKET:-}" ] && [ -n "${AWS_ACCESS_KEY_ID:-}" ] && [ -n "${AWS_SECRET_ACCESS_KEY:-}" ]; then
  echo "[*] Litestream: starting SQLite replication to S3/R2..."
  
  # Se o banco local não existe e a réplica existe, tenta restaurar
  if [ ! -f /data/ci.db ]; then
    echo "[*] Litestream: database not found. Restoring from replica..."
    litestream restore -config /etc/litestream.yml -if-db-not-exists -if-replica-exists /data/ci.db || echo "[!] Litestream: restore failed or no replica exists yet."
  fi
  
  # Executa a replicação embrulhando o processo do uvicorn
  exec litestream replicate -config /etc/litestream.yml -exec "uvicorn app:app --host 0.0.0.0 --port 8000"
else
  echo "[*] Litestream: replication not configured (missing env vars). Running uvicorn directly..."
  exec uvicorn app:app --host 0.0.0.0 --port 8000
fi
