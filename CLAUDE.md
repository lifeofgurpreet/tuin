# Evelien Garden - AI Agent Instructions

## Overview

Garden design visualization using Gemini nano-banana-pro-preview. Three-step pipeline: **Annotate** space photos, **Generate** designs, **Verify** against reality (self-healing loop).

## Tech Stack

| Component | Technology |
|-----------|------------|
| AI Model | Gemini nano-banana-pro-preview (only model with image editing) |
| Language | Python 3.x |
| Dependencies | google-genai, pillow, python-dotenv |

## Quick Commands

```bash
source venv/bin/activate

# Annotate space photos (do this first)
python scripts/annotate.py

# Generate a zone
python scripts/generate.py --zone shade
python scripts/generate.py --zone seating --count 3

# Full pipeline with self-healing
python scripts/pipeline.py --zone shade --max-retries 3

# Verify specific image
python scripts/verify.py --image generated/visuals/shade_v1.jpg
python scripts/verify.py --all
```

## Pipeline

```
ref/space/ photos
     |
     v
[annotate.py] -- Gemini labels features, dimensions, sun direction
     |
     v
generated/annotated/ (labeled photos)
     |
     +-- ref/inspiration/{zone}/ (style references)
     +-- drawings/layouts/ (top-down spatial plans)
     +-- generated/prompts/{zone}.md (editable instructions)
     |
     v
[generate.py] -- All images + prompt sent to Gemini
     |
     v
[verify.py] -- Compare output vs space photos
     |
     +-- PASS (40+/50) --> generated/visuals/
     +-- MARGINAL (30-39) --> kept, retry for better
     +-- REJECT (<30) --> generated/rejected/, retry
```

## Image Order in API Calls (CRITICAL)

1. Annotated space photos (grounds the design in reality)
2. Inspiration references (style direction)
3. Layout drawings (spatial plan)
4. Text prompt (instructions)

This order matters. Space photos MUST come first so the model understands the actual garden before seeing inspiration.

## Zones

| Zone | Folder | Prompt |
|------|--------|--------|
| shade | ref/inspiration/shade/ | generated/prompts/shade.md |
| plants | ref/inspiration/plants/ | generated/prompts/plants.md |
| seating | ref/inspiration/seating/ | generated/prompts/seating.md |
| play-area | ref/inspiration/play-area/ | generated/prompts/play-area.md |
| full | (samples from all) | generated/prompts/full.md |

## Editing Prompts

All prompts are markdown files in `generated/prompts/`. Edit them freely to steer output:
- `system_prompt.md` - Garden-wide rules and constraints
- `annotate_prompt.md` - How to label space photos
- `{zone}.md` - Zone-specific generation instructions
- `verify_prompt.md` - Verification scoring criteria

## Critical Rules

1. Always send space photos to Gemini - designs must match the actual garden
2. Annotate before generating - labeled photos produce better results
3. Never skip verification - the self-healing loop catches bad outputs
4. Rejected images are moved to generated/rejected/, not deleted
