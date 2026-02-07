#!/usr/bin/env bash
# ── Render Build Script ────────────────────────────
# This runs during Render's build phase

set -o errexit  # Exit on error

echo "══════════════════════════════════════════════"
echo "  Privacy Fortress — Build Step"
echo "══════════════════════════════════════════════"

# 1. Install Python dependencies
echo "[1/3] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 2. Download spaCy NER model (needed for PII detection)
echo "[2/3] Downloading spaCy NER model..."
python -m spacy download en_core_web_sm

# 3. Verify installation
echo "[3/3] Verifying setup..."
python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('[OK] spaCy model loaded')"
python -c "import fastapi; print(f'[OK] FastAPI {fastapi.__version__}')"
python -c "import motor; print('[OK] Motor (MongoDB async driver)')"
python -c "import redis; print('[OK] Redis client')"

echo ""
echo "══════════════════════════════════════════════"
echo "  Build complete!"
echo "══════════════════════════════════════════════"
