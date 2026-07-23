#!/usr/bin/env bash
# setup.sh — Development environment setup for LaAlbiceleste2026
# Run once after cloning: bash setup.sh
set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[setup]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $*"; }
error()   { echo -e "${RED}[error]${NC} $*"; exit 1; }

# ── Python version check ──────────────────────────────────────────────────────
info "Checking Python version..."
PYTHON=$(command -v python3 || command -v python || true)
[[ -z "$PYTHON" ]] && error "Python 3 not found. Install it from https://python.org and re-run."

PY_VER=$("$PYTHON" -c 'import sys; print("%d%d" % sys.version_info[:2])')
[[ "$PY_VER" -lt 38 ]] && error "Python 3.8+ required (found $("$PYTHON" --version))."
info "Using $("$PYTHON" --version)"

# ── Verify stdlib modules used by server.py ───────────────────────────────────
info "Verifying required stdlib modules..."
MODULES=(json os sys time urllib.request urllib.parse threading mimetypes
         http.server http.client hashlib uuid ssl base64 ipaddress re
         unicodedata random)
for mod in "${MODULES[@]}"; do
    "$PYTHON" -c "import $mod" 2>/dev/null || error "Module '$mod' missing from your Python installation."
done
info "All stdlib modules OK."

# ── Optional: create a virtual environment for future dependencies ────────────
if [[ -d ".venv" ]] && [[ ! -f ".venv/Scripts/activate" ]] && [[ ! -f ".venv/bin/activate" ]]; then
    warn ".venv/ exists but is incomplete — recreating..."
    rm -rf .venv
fi

if [[ ! -d ".venv" ]]; then
    info "Creating virtual environment in .venv/ ..."
    "$PYTHON" -m venv .venv
    info "Virtual environment created."
else
    warn ".venv/ already exists, skipping creation."
fi

# ── Activate venv and upgrade pip (no-op for current server, useful for devs) ─
if [[ -f ".venv/Scripts/activate" ]]; then
    source .venv/Scripts/activate
elif [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
else
    error "Could not find venv activate script in .venv/Scripts/ or .venv/bin/."
fi
info "Upgrading pip..."
pip install --quiet --upgrade pip

# ── Install optional dev tools if a requirements-dev.txt exists ───────────────
if [[ -f requirements-dev.txt ]]; then
    info "Installing dev dependencies from requirements-dev.txt..."
    pip install --quiet -r requirements-dev.txt
fi

# ── Verify config.json is valid JSON ─────────────────────────────────────────
info "Validating config.json..."
"$PYTHON" -c "import json; json.load(open('config.json'))" || error "config.json is not valid JSON."
info "config.json OK."

# ── Verify any existing data/*.json files are valid JSON ─────────────────────
# (missing files are fine — server.py creates them with sane defaults on first use)
if [[ -d data ]]; then
    info "Validating existing data/*.json files..."
    for f in data/*.json; do
        [[ -e "$f" ]] || continue
        "$PYTHON" -c "import json,sys; json.load(open(sys.argv[1]))" "$f" || error "$f is not valid JSON."
    done
    info "data/*.json OK."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "  To start the server:"
echo "    source .venv/Scripts/activate  # Windows"
echo "    source .venv/bin/activate      # Linux/macOS"
echo "    python3 server.py          # port 8000"
echo "    python3 server.py 8080     # custom port"
echo ""
echo "  Then open http://localhost:8000 in your browser — it routes to the group-stage"
echo "  or knockout-stage game automatically (see stage_redirect in config.json)."
echo ""
echo "  All app state lives in data/*.json (no database to install)."
echo "  To make a user an admin, set \"isAdmin\": true for them in data/users.json,"
echo "  then reach the control panel at http://localhost:8000/admin.html."
