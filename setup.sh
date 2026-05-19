#!/usr/bin/env bash
# setup.sh — Development environment setup for nesine-soccer-api
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
MODULES=(json os sys time urllib threading mimetypes http.server)
for mod in "${MODULES[@]}"; do
    "$PYTHON" -c "import $mod" 2>/dev/null || error "Module '$mod' missing from your Python installation."
done
info "All stdlib modules OK."

# ── Optional: create a virtual environment for future dependencies ────────────
if [[ ! -d ".venv" ]]; then
    info "Creating virtual environment in .venv/ ..."
    "$PYTHON" -m venv .venv
    info "Virtual environment created."
else
    warn ".venv/ already exists, skipping creation."
fi

# ── Activate venv and upgrade pip (no-op for current server, useful for devs) ─
source .venv/bin/activate
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

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "  To start the server:"
echo "    source .venv/bin/activate"
echo "    python3 server.py          # port 3000"
echo "    python3 server.py 8080     # custom port"
echo ""
echo "  Then open http://localhost:3000 in your browser."
