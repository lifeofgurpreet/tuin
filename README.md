# Evelien Garden

AI-powered garden design visualization using Gemini's image generation. Generates consistent visuals for shade structures, planting, seating areas, and children's play spaces based on reference photos and inspiration images.

## Quick Start

```bash
cp .env.example .env          # Add GEMINI_API_KEY
python -m venv venv && source venv/bin/activate
pip install google-genai pillow python-dotenv

# 1. Add photos of your garden to ref/space/
# 2. Add inspiration images to ref/inspiration/{zone}/
# 3. Run the pipeline:

python scripts/annotate.py                        # Annotate space photos
python scripts/pipeline.py --zone shade --max-retries 3  # Generate with self-healing
```

## Pipeline

**Annotate** (label space photos) -> **Generate** (create designs) -> **Verify** (check against real space) -> retry if rejected

See [AGENTS.md](AGENTS.md) for full documentation.
