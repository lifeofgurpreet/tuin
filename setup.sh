#!/bin/bash
# Evelien Garden - Quick Setup
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=== Evelien Garden Setup ==="
echo ""

# 1. Python venv
if [ ! -d "venv" ]; then
    echo "[*] Creating Python virtual environment..."
    python3 -m venv venv
else
    echo "[OK] venv exists"
fi

source venv/bin/activate

# 2. Dependencies
echo "[*] Installing dependencies..."
pip install -q google-genai pillow python-dotenv

# 3. .env file
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "[!] Created .env from .env.example"
    echo "    Edit .env and add your GEMINI_API_KEY"
else
    echo "[OK] .env exists"
fi

# 4. Check API key
if grep -q "your-api-key-here" .env 2>/dev/null; then
    echo ""
    echo "[!] GEMINI_API_KEY not configured yet."
    echo "    Edit .env and replace 'your-api-key-here' with your actual key."
    echo ""
fi

# 5. Check for photos
SPACE_COUNT=$(find ref/space -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" -o -name "*.heic" \) 2>/dev/null | wc -l)
INSPO_COUNT=$(find ref/inspiration -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" \) 2>/dev/null | wc -l)

echo ""
echo "=== Status ==="
echo "Space photos:       $SPACE_COUNT (add to ref/space/)"
echo "Inspiration images: $INSPO_COUNT (add to ref/inspiration/{shade,plants,seating,play-area}/)"
echo ""

if [ "$SPACE_COUNT" -gt 0 ] && ! grep -q "your-api-key-here" .env 2>/dev/null; then
    echo "[READY] Run the pipeline:"
    echo "  source venv/bin/activate"
    echo "  python scripts/pipeline.py --zone shade --max-retries 3"
else
    echo "[NEXT STEPS]"
    [ "$SPACE_COUNT" -eq 0 ] && echo "  1. Add garden photos to ref/space/"
    grep -q "your-api-key-here" .env 2>/dev/null && echo "  2. Add GEMINI_API_KEY to .env"
    echo "  3. Run: python scripts/pipeline.py --zone shade --max-retries 3"
fi
