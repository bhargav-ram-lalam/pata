#!/usr/bin/env bash
# =============================================================================
# scripts/preflight_check.sh
# Pata Demo Pre-Flight Checklist
# =============================================================================
# Run this script BEFORE walking on stage.
# Prints a clear ✅/❌ checklist — not raw logs.
# Exits 0 if everything is ready; non-zero otherwise.
#
# Usage:
#   bash scripts/preflight_check.sh
#   bash scripts/preflight_check.sh --api-url http://your-host:8000 --api-key your_key
#
# Defaults (override with flags):
#   API_URL   = http://localhost:8000
#   API_KEY   = pata_dev_key
#   FRONTEND1 = http://localhost:5173  (Playground)
#   FRONTEND2 = http://localhost:5174  (Review Dashboard)
# =============================================================================

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
API_URL="${PATA_API_URL:-http://localhost:8000}"
API_KEY="${PATA_API_KEY:-pata_dev_key}"
FRONTEND1="${PATA_PLAYGROUND_URL:-http://localhost:5173}"
FRONTEND2="${PATA_DASHBOARD_URL:-http://localhost:5174}"
TIMEOUT=5  # seconds per check

PASS=0
FAIL=0

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
RESET='\033[0m'
BOLD='\033[1m'

ok()   { echo -e "  ${GREEN}✅${RESET}  $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}❌${RESET}  $1"; FAIL=$((FAIL + 1)); }
warn() { echo -e "  ${YELLOW}⚠️ ${RESET}  $1"; }
hdr()  { echo -e "\n${BOLD}$1${RESET}"; }

# ── Parse flags ───────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url)   API_URL="$2";   shift 2 ;;
    --api-key)   API_KEY="$2";   shift 2 ;;
    --frontend1) FRONTEND1="$2"; shift 2 ;;
    --frontend2) FRONTEND2="$2"; shift 2 ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Pata (पता) — Demo Pre-Flight Checklist   ${RESET}"
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
echo "  API:        $API_URL"
echo "  Playground: $FRONTEND1"
echo "  Dashboard:  $FRONTEND2"
echo ""

# ── 1. Backend liveness ──────────────────────────────────────────────────────
hdr "Backend Connectivity"

http_status=$(curl -s -o /dev/null -w "%{http_code}" \
  --max-time "$TIMEOUT" "${API_URL}/v1/health/live" 2>/dev/null || echo "000")

if [[ "$http_status" == "200" ]]; then
  ok "Backend /v1/health/live → HTTP $http_status"
else
  fail "Backend /v1/health/live → HTTP $http_status (expected 200)"
fi

# ── 2. Backend readiness (models loaded) ─────────────────────────────────────
ready_status=$(curl -s -o /dev/null -w "%{http_code}" \
  --max-time "$TIMEOUT" "${API_URL}/v1/health/ready" 2>/dev/null || echo "000")

if [[ "$ready_status" == "200" ]]; then
  ok "Backend /v1/health/ready → HTTP $ready_status (models loaded)"
else
  fail "Backend /v1/health/ready → HTTP $ready_status (models may still be loading — wait 60–90s and retry)"
fi

# ── 3. Detailed subsystem health ──────────────────────────────────────────────
hdr "Subsystem Health (via /v1/health)"

health_json=$(curl -s --max-time "$TIMEOUT" \
  -H "X-API-Key: $API_KEY" \
  "${API_URL}/v1/health" 2>/dev/null || echo '{}')

# Detect python binary
PY_CMD="python3"
if ! command -v python3 >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    PY_CMD="python"
  elif command -v py >/dev/null 2>&1; then
    PY_CMD="py"
  fi
fi

# Parse components with JSON parser
check_component() {
  local label="$1"
  local key="$2"
  if echo "$health_json" | grep -q "\"$key\"" 2>/dev/null; then
    local val
    val=$(echo "$health_json" | $PY_CMD -c \
      "import sys,json; d=json.load(sys.stdin); c=d.get('components',{}); print(c.get('$key',{}).get('status','missing'))" \
      2>/dev/null || echo "unknown")
    if [[ "$val" == "healthy" ]]; then
      ok "$label → $val"
    elif [[ "$val" == "degraded" ]]; then
      warn "$label → $val (non-fatal, demo mode handles fallback)"
    else
      fail "$label → $val"
    fi
  else
    fail "$label → component missing from health response"
  fi
}

check_component "PostgreSQL (bharataddress parser)" "bharataddress_parser"
check_component "IndicBERT NER model (warm in memory)" "indicbert_ner_model"
check_component "Overpass circuit breaker" "overpass_api"
check_component "LLM provider key configured" "llm_provider"

# ── 4. Frontend servers ───────────────────────────────────────────────────────
hdr "Frontend Servers"

pg_status=$(curl -s -o /dev/null -w "%{http_code}" \
  --max-time "$TIMEOUT" "$FRONTEND1" 2>/dev/null || echo "000")
if [[ "$pg_status" == "200" ]]; then
  ok "Playground ($FRONTEND1) → HTTP $pg_status"
else
  fail "Playground ($FRONTEND1) → HTTP $pg_status (not responding)"
fi

db_status=$(curl -s -o /dev/null -w "%{http_code}" \
  --max-time "$TIMEOUT" "$FRONTEND2" 2>/dev/null || echo "000")
if [[ "$db_status" == "200" ]]; then
  ok "Review Dashboard ($FRONTEND2) → HTTP $db_status"
else
  fail "Review Dashboard ($FRONTEND2) → HTTP $db_status (not responding)"
fi

# ── 5. Demo mode status ───────────────────────────────────────────────────────
hdr "Demo Configuration"

if [[ "${PATA_DEMO_MODE:-}" == "1" ]]; then
  ok "PATA_DEMO_MODE=1 — benchmark addresses will use pre-recorded responses (offline-safe)"
else
  warn "PATA_DEMO_MODE is not set — live Overpass + LLM calls will be made (requires network)"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Summary: $PASS passed, $FAIL failed          ${RESET}"
echo -e "${BOLD}════════════════════════════════════════════${RESET}"

if [[ "$FAIL" -eq 0 ]]; then
  echo -e "\n  ${GREEN}${BOLD}✈  READY TO DEMO — all systems go!${RESET}\n"
  exit 0
else
  echo -e "\n  ${RED}${BOLD}⚠  NOT READY — fix the $FAIL issue(s) above first.${RESET}\n"
  echo "  Quick fixes:"
  echo "    Backend down?  →  docker-compose -f docker-compose.demo.yml up -d"
  echo "    Model cold?   →  Wait 60–90s, then re-run this script"
  echo "    Frontends?    →  cd frontend/playground && npm run dev  (port 5173)"
  echo "                     cd frontend/review-dashboard && npm run dev  (port 5174)"
  echo "    WiFi down?    →  export PATA_DEMO_MODE=1 and restart the API"
  echo ""
  exit 1
fi
