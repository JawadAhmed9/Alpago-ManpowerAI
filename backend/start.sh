#!/bin/sh
set -e

echo "[start] running migrations"
alembic upgrade head

if [ "${SEED_ON_STARTUP:-false}" = "true" ]; then
  echo "[start] seeding sample data from TechnicalTest_2.xlsx (idempotent)"
  python -m app.seed.seed
fi

echo "[start] launching API on port ${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
