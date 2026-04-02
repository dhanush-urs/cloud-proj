#!/usr/bin/env bash
set -Eeuo pipefail

# =========================================
# RepoBrain Production QA Smoke Script
# Run from project root
# =========================================

ROOT_DIR="$(pwd)"
LOG_DIR="$ROOT_DIR/qa_logs_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"

API_DIR="$ROOT_DIR/apps/api"
WEB_DIR="$ROOT_DIR/apps/web"
COMPOSE_FILE="$ROOT_DIR/infra/compose/docker-compose.prod.yml"

API_HOST="127.0.0.1"
API_PORT="8000"
WEB_HOST="127.0.0.1"
WEB_PORT="3000"

API_PID=""
WEB_PID=""

# -------- colors --------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# -------- helpers --------
log() {
  echo -e "${BLUE}[INFO]${NC} $*"
}

warn() {
  echo -e "${YELLOW}[WARN]${NC} $*"
}

ok() {
  echo -e "${GREEN}[PASS]${NC} $*"
}

fail() {
  echo -e "${RED}[FAIL]${NC} $*" >&2
  exit 1
}

section() {
  echo
  echo -e "${BLUE}==================================================${NC}"
  echo -e "${BLUE}$*${NC}"
  echo -e "${BLUE}==================================================${NC}"
}

run() {
  echo
  echo -e "${BLUE}>> $*${NC}"
  "$@"
}

run_log() {
  local logfile="$1"
  shift
  echo
  echo -e "${BLUE}>> $*${NC}"
  "$@" 2>&1 | tee "$logfile"
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

cleanup() {
  section "CLEANUP"

  if [[ -n "${API_PID}" ]] && kill -0 "${API_PID}" 2>/dev/null; then
    warn "Stopping backend PID ${API_PID}"
    kill "${API_PID}" || true
  fi

  if [[ -n "${WEB_PID}" ]] && kill -0 "${WEB_PID}" 2>/dev/null; then
    warn "Stopping frontend PID ${WEB_PID}"
    kill "${WEB_PID}" || true
  fi

  if [[ -f "$COMPOSE_FILE" ]] && has_cmd docker; then
    warn "Cleaning up local background processes (Docker remains up for inspection)"
    # docker compose -f "$COMPOSE_FILE" down > "$LOG_DIR/docker_down.log" 2>&1 || true
  fi
}
trap cleanup EXIT

wait_for_http() {
  local url="$1"
  local max_attempts="${2:-20}"
  local sleep_seconds="${3:-2}"

  for ((i=1; i<=max_attempts; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$sleep_seconds"
  done
  return 1
}

wait_for_tcp() {
  local host="$1"
  local port="$2"
  local max_attempts="${3:-20}"
  local sleep_seconds="${4:-2}"

  for ((i=1; i<=max_attempts; i++)); do
    if (echo > /dev/tcp/"$host"/"$port") >/dev/null 2>&1; then
      return 0
    fi
    sleep "$sleep_seconds"
  done
  return 1
}

# =========================================
# 1) BASIC STRUCTURE CHECK
# =========================================
section "1) BASIC STRUCTURE CHECK"

[[ -d "$API_DIR" ]] || fail "Missing $API_DIR"
[[ -d "$WEB_DIR" ]] || fail "Missing $WEB_DIR"
[[ -f "$COMPOSE_FILE" ]] || fail "Missing $COMPOSE_FILE"

ok "Project structure looks valid"

# =========================================
# 2) TOOLING CHECK
# =========================================
section "2) TOOLING CHECK"

has_cmd python3 || fail "python3 not found"
has_cmd curl || fail "curl not found"

if has_cmd docker; then
  ok "docker found"
else
  warn "docker not found (Docker checks will be skipped)"
fi

if has_cmd npm; then
  ok "npm found"
else
  fail "npm not found"
fi

# =========================================
# 3) BACKEND SETUP
# =========================================
section "3) BACKEND SETUP"

cd "$API_DIR"

if [[ ! -d ".venv" ]]; then
  log "Creating backend virtualenv"
  run_log "$LOG_DIR/backend_venv_create.log" python3 -m venv .venv
else
  ok "Backend .venv already exists"
fi

[[ -x ".venv/bin/python" ]] || fail "Backend venv python not found at apps/api/.venv/bin/python"

run_log "$LOG_DIR/backend_pip_upgrade.log" .venv/bin/pip install --upgrade pip

if [[ -f "requirements.txt" ]]; then
  run_log "$LOG_DIR/backend_pip_install.log" .venv/bin/pip install -r requirements.txt
else
  fail "apps/api/requirements.txt not found"
fi

ok "Backend dependencies installed"

# =========================================
# 4) BACKEND IMPORT SMOKE
# =========================================
section "4) BACKEND IMPORT SMOKE"

run_log "$LOG_DIR/backend_import_smoke.log" .venv/bin/python -c "import app.main; print('backend import OK')"
ok "Backend import smoke passed"

# =========================================
# 5) BACKEND ENV FILE CHECK
# =========================================
section "5) BACKEND ENV FILE CHECK"

if [[ -f ".env" ]]; then
  ok "apps/api/.env exists"
else
  if [[ -f ".env.sample" ]]; then
    warn "apps/api/.env missing; copying from .env.sample"
    cp .env.sample .env
    ok "Created apps/api/.env from .env.sample"
  elif [[ -f ".env.example" ]]; then
    warn "apps/api/.env missing; copying from .env.example"
    cp .env.example .env
    ok "Created apps/api/.env from .env.example"
  else
    warn "No backend .env found and no sample/example found. Proceeding, but config may fail."
  fi
fi

# =========================================
# 6) ALEMBIC MIGRATIONS
# =========================================
section "6) ALEMBIC MIGRATIONS"

if [[ -f "alembic.ini" ]] || [[ -d "alembic" ]]; then
  if .venv/bin/python -m alembic upgrade head 2>&1 | tee "$LOG_DIR/alembic_upgrade.log"; then
    ok "Alembic upgrade head passed"
  else
    fail "Alembic upgrade head failed. See $LOG_DIR/alembic_upgrade.log"
  fi
else
  warn "Alembic config not found in apps/api. Skipping migration check."
fi

# =========================================
# 7) BACKEND BOOT (SIMPLE SMOKE)
# =========================================
section "7) BACKEND BOOT (SIMPLE SMOKE)"

# Since timeout is missing on macOS, we'll run uvicorn in background, wait, then kill it.
log "Starting backend for a 15s smoke test..."
nohup .venv/bin/python -m uvicorn app.main:app --host "$API_HOST" --port "$API_PORT" > "$LOG_DIR/backend_timeout_boot.log" 2>&1 &
TEMP_BOOT_PID=$!
sleep 15

if kill -0 "$TEMP_BOOT_PID" 2>/dev/null; then
  ok "Backend stayed up during smoke test window (good sign)"
  kill "$TEMP_BOOT_PID" || true
else
  cat "$LOG_DIR/backend_timeout_boot.log" || true
  fail "Backend crashed during smoke test. See $LOG_DIR/backend_timeout_boot.log"
fi

# =========================================
# 8) BACKEND BOOT (BACKGROUND)
# =========================================
section "8) BACKEND BOOT (BACKGROUND)"

nohup .venv/bin/python -m uvicorn app.main:app --host "$API_HOST" --port "$API_PORT" \
  > "$LOG_DIR/backend_bg.log" 2>&1 &
API_PID=$!
sleep 5

if kill -0 "$API_PID" 2>/dev/null; then
  ok "Backend started in background (PID $API_PID)"
else
  cat "$LOG_DIR/backend_bg.log" || true
  fail "Backend failed to stay up in background. See $LOG_DIR/backend_bg.log"
fi

if wait_for_tcp "$API_HOST" "$API_PORT" 20 1; then
  ok "Backend port $API_PORT is reachable"
else
  cat "$LOG_DIR/backend_bg.log" || true
  fail "Backend port $API_PORT not reachable"
fi

# =========================================
# 9) HEALTH ENDPOINTS
# =========================================
section "9) HEALTH ENDPOINTS"

run_log "$LOG_DIR/health.log" curl -i "http://$API_HOST:$API_PORT/api/v1/health"
run_log "$LOG_DIR/health_live.log" curl -i "http://$API_HOST:$API_PORT/api/v1/health/live"
run_log "$LOG_DIR/health_ready.log" curl -i "http://$API_HOST:$API_PORT/api/v1/health/ready"

ok "Health endpoint checks executed (inspect logs for status codes if needed)"

# =========================================
# 10) OPENAPI ROUTE DISCOVERY
# =========================================
section "10) OPENAPI ROUTE DISCOVERY"

if curl -fsS "http://$API_HOST:$API_PORT/openapi.json" > "$LOG_DIR/openapi.json"; then
  ok "Fetched openapi.json"
  python3 - <<PY | tee "$LOG_DIR/openapi_paths.txt"
import json
from pathlib import Path
p = Path("$LOG_DIR/openapi.json")
data = json.loads(p.read_text())
for path in sorted(data.get("paths", {}).keys()):
    print(path)
PY
  ok "Saved route list to $LOG_DIR/openapi_paths.txt"
else
  warn "Could not fetch openapi.json"
fi

# =========================================
# 11) BACKEND TESTS
# =========================================
section "11) BACKEND TESTS"

cd "$API_DIR"

if [[ -d "tests" ]]; then
  # Run health tests first if present
  if [[ -f "tests/test_health.py" ]]; then
    run_log "$LOG_DIR/pytest_test_health.log" .venv/bin/python -m pytest -q -x -s tests/test_health.py
    ok "tests/test_health.py passed"
  else
    warn "tests/test_health.py not found"
  fi

  # Run repos tests if present
  if [[ -f "tests/test_repos.py" ]]; then
    run_log "$LOG_DIR/pytest_test_repos.log" .venv/bin/python -m pytest -q -x -s tests/test_repos.py
    ok "tests/test_repos.py passed"
  else
    warn "tests/test_repos.py not found"
  fi

  # Full test suite
  run_log "$LOG_DIR/pytest_full.log" .venv/bin/python -m pytest -q -x
  ok "Full backend pytest suite passed"
else
  warn "apps/api/tests not found. Skipping backend tests."
fi

# =========================================
# 12) FRONTEND INSTALL
# =========================================
section "12) FRONTEND INSTALL"

cd "$WEB_DIR"

if [[ -f "package-lock.json" ]]; then
  run_log "$LOG_DIR/frontend_npm_ci.log" npm ci
else
  warn "package-lock.json not found; using npm install"
  run_log "$LOG_DIR/frontend_npm_install.log" npm install
fi

ok "Frontend dependencies installed"

# =========================================
# 13) FRONTEND BUILD
# =========================================
section "13) FRONTEND BUILD"

run_log "$LOG_DIR/frontend_build.log" npm run build
ok "Frontend build passed"

# =========================================
# 14) FRONTEND LINT / FORMAT (IF AVAILABLE)
# =========================================
section "14) FRONTEND LINT / FORMAT"

if grep -q '"lint"' package.json; then
  run_log "$LOG_DIR/frontend_lint.log" npm run lint
  ok "Frontend lint passed"
else
  warn "No lint script found in package.json"
fi

if grep -q '"format:check"' package.json; then
  run_log "$LOG_DIR/frontend_format_check.log" npm run format:check
  ok "Frontend format:check passed"
else
  warn "No format:check script found in package.json"
fi

# =========================================
# 15) FRONTEND BOOT (BACKGROUND)
# =========================================
section "15) FRONTEND BOOT (BACKGROUND)"

nohup npm run dev > "$LOG_DIR/frontend_bg.log" 2>&1 &
WEB_PID=$!
sleep 8

if kill -0 "$WEB_PID" 2>/dev/null; then
  ok "Frontend started in background (PID $WEB_PID)"
else
  cat "$LOG_DIR/frontend_bg.log" || true
  fail "Frontend failed to stay up in background. See $LOG_DIR/frontend_bg.log"
fi

if wait_for_http "http://$WEB_HOST:$WEB_PORT" 30 2; then
  ok "Frontend is reachable at http://$WEB_HOST:$WEB_PORT"
else
  cat "$LOG_DIR/frontend_bg.log" || true
  fail "Frontend did not become reachable"
fi

run_log "$LOG_DIR/frontend_head_root.log" curl -I "http://$WEB_HOST:$WEB_PORT"

# Optional /repos route check
if curl -I "http://$WEB_HOST:$WEB_PORT/repos" > "$LOG_DIR/frontend_head_repos.log" 2>&1; then
  ok "Frontend /repos route responded"
else
  warn "Frontend /repos route did not respond (may not exist in your app)"
fi

# =========================================
# 16) DOCKER PROD BUILD / UP / PS / LOGS / HEALTH
# =========================================
section "16) DOCKER PROD BUILD / UP / PS / LOGS / HEALTH"

if has_cmd docker; then
  cd "$ROOT_DIR"

  run_log "$LOG_DIR/docker_build.log" docker compose -f "$COMPOSE_FILE" build
  ok "Docker compose build passed"

  run_log "$LOG_DIR/docker_up.log" docker compose -f "$COMPOSE_FILE" up -d
  ok "Docker compose up -d executed"

  run_log "$LOG_DIR/docker_ps.log" docker compose -f "$COMPOSE_FILE" ps

  # Give services time
  sleep 10

  run_log "$LOG_DIR/docker_logs_db.log" docker compose -f "$COMPOSE_FILE" logs --tail=100 db
  run_log "$LOG_DIR/docker_logs_api.log" docker compose -f "$COMPOSE_FILE" logs --tail=100 api
  run_log "$LOG_DIR/docker_logs_web.log" docker compose -f "$COMPOSE_FILE" logs --tail=100 web

  # Health checks against host ports
  if curl -fsS "http://$API_HOST:$API_PORT/api/v1/health" > "$LOG_DIR/docker_health_api.json" 2>/dev/null; then
    ok "Docker API /health reachable"
  else
    warn "Docker API /health not reachable on host port $API_PORT"
  fi

  if curl -fsS "http://$API_HOST:$API_PORT/api/v1/health/live" > "$LOG_DIR/docker_health_live.json" 2>/dev/null; then
    ok "Docker API /health/live reachable"
  else
    warn "Docker API /health/live not reachable"
  fi

  if curl -fsS "http://$API_HOST:$API_PORT/api/v1/health/ready" > "$LOG_DIR/docker_health_ready.json" 2>/dev/null; then
    ok "Docker API /health/ready reachable"
  else
    warn "Docker API /health/ready not reachable"
  fi

  if curl -I "http://$WEB_HOST:$WEB_PORT" > "$LOG_DIR/docker_frontend_head.log" 2>&1; then
    ok "Docker frontend reachable on host port $WEB_PORT"
  else
    warn "Docker frontend not reachable on host port $WEB_PORT"
  fi
else
  warn "Skipping Docker checks because docker is not installed"
fi

# =========================================
# 17) GITHUB ACTIONS WORKFLOW CHECK
# =========================================
section "17) GITHUB ACTIONS WORKFLOW CHECK"

cd "$ROOT_DIR"

if [[ -d ".github/workflows" ]]; then
  find .github/workflows -type f | sort | tee "$LOG_DIR/github_workflows_list.txt"
  while IFS= read -r wf; do
    echo "===== $wf =====" >> "$LOG_DIR/github_workflows_dump.txt"
    sed -n '1,260p' "$wf" >> "$LOG_DIR/github_workflows_dump.txt"
    echo >> "$LOG_DIR/github_workflows_dump.txt"
  done < <(find .github/workflows -type f | sort)
  ok "Captured GitHub Actions workflow files"
else
  warn ".github/workflows not found"
fi

# =========================================
# 18) SUMMARY
# =========================================
section "18) SUMMARY"

cat <<SUMMARY
QA smoke script completed.

Logs directory:
  $LOG_DIR

Key files to inspect if anything failed:
  - $LOG_DIR/backend_import_smoke.log
  - $LOG_DIR/alembic_upgrade.log
  - $LOG_DIR/backend_timeout_boot.log
  - $LOG_DIR/backend_bg.log
  - $LOG_DIR/health.log
  - $LOG_DIR/health_live.log
  - $LOG_DIR/health_ready.log
  - $LOG_DIR/pytest_full.log
  - $LOG_DIR/frontend_build.log
  - $LOG_DIR/frontend_lint.log
  - $LOG_DIR/frontend_format_check.log
  - $LOG_DIR/frontend_bg.log
  - $LOG_DIR/docker_build.log
  - $LOG_DIR/docker_up.log
  - $LOG_DIR/docker_ps.log
  - $LOG_DIR/docker_logs_api.log
  - $LOG_DIR/docker_logs_web.log
  - $LOG_DIR/github_workflows_dump.txt

If the script exited early, the failing step is the first place to inspect.
SUMMARY

ok "RepoBrain QA smoke completed"
