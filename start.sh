#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Apply database migrations before the app accepts traffic.
alembic upgrade head

# Production mode serves frontend and backend on one port (reflex.frontend_port).
exec reflex run --env prod --single-port
