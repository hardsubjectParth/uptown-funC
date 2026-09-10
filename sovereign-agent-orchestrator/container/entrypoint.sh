#!/bin/sh
set -eu

POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-orchestrator}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}"
POSTGRES_DB="${POSTGRES_DB:-orchestrator}"
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_HOST
export OLLAMA_NO_CLOUD=true

if [ "$(id -u)" -eq 0 ]; then
  mkdir -p /var/run/postgresql /var/lib/postgresql/data
  chown -R postgres:postgres /var/run/postgresql /var/lib/postgresql/data
  if [ ! -s /var/lib/postgresql/data/PG_VERSION ]; then
    gosu postgres initdb -D /var/lib/postgresql/data --auth-local=trust --auth-host=scram-sha-256
  fi
  gosu postgres postgres -D /var/lib/postgresql/data -p "$POSTGRES_PORT" -c listen_addresses=127.0.0.1 &
  postgres_pid=$!
else
  echo 'Container entrypoint must start as root' >&2
  exit 1
fi

cleanup() {
  kill ${api_pid:-} ${worker_pid:-} ${ollama_pid:-} ${postgres_pid:-} 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

until gosu postgres pg_isready -p "$POSTGRES_PORT" >/dev/null 2>&1; do sleep 1; done

gosu postgres psql -p "$POSTGRES_PORT" -d postgres -v ON_ERROR_STOP=1 \
  -v app_user="$POSTGRES_USER" -v app_password="$POSTGRES_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user')\gexec
SELECT format('ALTER ROLE %I PASSWORD %L', :'app_user', :'app_password')\gexec
SQL

for database in "$POSTGRES_DB" rag_admin rag_higher rag_lower; do
  if ! gosu postgres psql -p "$POSTGRES_PORT" -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='${database}'" | grep -q 1; then
    gosu postgres createdb -p "$POSTGRES_PORT" -O "$POSTGRES_USER" "$database"
  fi
done

gosu postgres psql -p "$POSTGRES_PORT" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f migrations/core/001_operational.sql
for database in rag_admin rag_higher rag_lower; do
  gosu postgres psql -p "$POSTGRES_PORT" -d "$database" -v ON_ERROR_STOP=1 -f migrations/tier/001_initial_pgvector.sql
done

for database in "$POSTGRES_DB" rag_admin rag_higher rag_lower; do
  gosu postgres psql -p "$POSTGRES_PORT" -d "$database" -v ON_ERROR_STOP=1 \
    -v app_user="$POSTGRES_USER" <<'SQL'
GRANT USAGE, CREATE ON SCHEMA public TO :"app_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app_user";
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO :"app_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO :"app_user";
SQL
done

export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}"
export ADMIN_DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/rag_admin"
export HIGHER_DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/rag_higher"
export LOWER_DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/rag_lower"
export REQUIRE_POSTGRES=true
export MODEL_MODE="${MODEL_MODE:-ollama}"
export OLLAMA_BASE_URL="http://${OLLAMA_HOST}"
export WORKSPACE_ROOT="${WORKSPACE_ROOT:-/opt/workspace}"
export RUN_WORKER=false

ollama serve &
ollama_pid=$!

if [ "${OLLAMA_PULL_ON_START:-false}" = "true" ]; then
  ollama pull "${OLLAMA_MODEL:-qwen2.5vl:3b}"
  ollama pull "${OLLAMA_EMBEDDING_MODEL:-nomic-embed-text}"
  for model in ${OLLAMA_EXTRA_MODELS:-}; do
    ollama pull "$model"
  done
fi

gosu app /opt/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${API_PORT:-8080}" &
api_pid=$!
gosu app /opt/venv/bin/python -m app.worker &
worker_pid=$!

while kill -0 "$api_pid" 2>/dev/null && kill -0 "$worker_pid" 2>/dev/null && kill -0 "$postgres_pid" 2>/dev/null; do
  sleep 2
done
exit 1