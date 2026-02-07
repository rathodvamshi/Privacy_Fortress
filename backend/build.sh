#!/usr/bin/env bash
# ── Render Build Script — Optimized for Speed ─────
set -o errexit  # Exit on error

echo "══════════════════════════════════════════════"
echo "  Privacy Fortress — Build Step"
echo "══════════════════════════════════════════════"

# 1. Upgrade pip + install deps with caching
echo "[1/4] Installing Python dependencies..."
pip install --upgrade pip setuptools wheel --quiet
pip install -r requirements.txt --no-cache-dir --quiet

# 2. Download spaCy model — use direct pip install (most reliable on Render)
echo "[2/4] Downloading spaCy NER model..."
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl --quiet

# 3. Preload & warm models so first request is instant
echo "[3/4] Preloading models for fast cold start..."
python -c "
import spacy
nlp = spacy.load('en_core_web_sm')
doc = nlp('Test warmup sentence for Privacy Fortress.')
print(f'[OK] spaCy loaded + warmed ({len(nlp.pipe_names)} pipes)')
"

# 4. Quick verification
echo "[4/4] Verifying installation..."
python -c "
import fastapi, motor, redis, cryptography, groq
print(f'[OK] FastAPI {fastapi.__version__}')
print('[OK] All core packages verified')
"

echo ""
echo "══════════════════════════════════════════════"
echo "  Build complete — ready to serve!"
echo "══════════════════════════════════════════════"
