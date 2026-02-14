# Evelien Garden - AI Agent Instructions

## Project Overview

AI-powered garden design visualization using Gemini (nano-banana-pro-preview) to generate consistent garden shade, seating, planting, and play area designs based on reference photos and inspiration images.

## Tech Stack

| Component | Technology |
|-----------|------------|
| AI Model | Gemini nano-banana-pro-preview |
| Language | Python 3.x |
| Dependencies | google-genai, pillow, python-dotenv |

## Pipeline: Annotate -> Generate -> Verify

```
1. ANNOTATE  (scripts/annotate.py)
   Send space photos to Gemini -> get labeled annotations
   (dimensions, sun direction, existing features, boundaries)

2. GENERATE  (scripts/generate.py)
   Send annotated photos + inspiration refs + layout drawings + prompts
   -> Gemini generates design visuals

3. VERIFY    (scripts/verify.py)
   Send generated image + original space photo to Gemini
   -> "Does this match the actual space?" -> reject if mismatch

4. PIPELINE  (scripts/pipeline.py)
   Full cycle: annotate -> generate -> verify -> retry if rejected
```

## Key Commands

```bash
# Setup
cp .env.example .env  # Add your GEMINI_API_KEY
python -m venv venv && source venv/bin/activate
pip install google-genai pillow python-dotenv

# Annotate space photos first
python scripts/annotate.py

# Generate designs for a zone
python scripts/generate.py --zone shade
python scripts/generate.py --zone seating
python scripts/generate.py --zone play-area
python scripts/generate.py --zone plants
python scripts/generate.py --zone full  # Complete garden

# Full pipeline with self-healing
python scripts/pipeline.py --zone shade --max-retries 3

# Verify a specific generated image
python scripts/verify.py --image generated/visuals/shade_v1.jpg
```

## Directory Structure

```
evelien/
├── ref/                      # Reference inputs (DO NOT modify originals)
│   ├── space/                # Current photos of the actual garden
│   └── inspiration/          # Style/mood references
│       ├── shade/            # Shade structure references
│       ├── plants/           # Planting references
│       ├── seating/          # Seating area references
│       └── play-area/        # Children's play area references
│
├── drawings/                 # Architectural drawings & layouts
│   ├── layouts/              # Top-down views of the garden
│   └── sections/             # Cross-section views
│
├── generated/                # AI-generated content
│   ├── prompts/              # Editable prompts (EDIT THESE)
│   │   ├── system_prompt.md  # Garden rules & constraints
│   │   ├── annotate_prompt.md # How to annotate space photos
│   │   ├── shade.md          # Shade zone generation prompt
│   │   ├── seating.md        # Seating zone generation prompt
│   │   ├── plants.md         # Plants zone generation prompt
│   │   ├── play-area.md      # Play area generation prompt
│   │   ├── full.md           # Full garden generation prompt
│   │   └── verify_prompt.md  # Self-healing verification prompt
│   ├── annotated/            # Annotated versions of space photos
│   ├── visuals/              # Final generated designs
│   ├── rejected/             # Failed verification (for review)
│   └── feedback/             # Generation logs & notes
│
└── scripts/                  # Python tools
    ├── annotate.py           # Step 1: Annotate reference photos
    ├── generate.py           # Step 2: Generate designs
    ├── verify.py             # Step 3: Self-healing verification
    └── pipeline.py           # Full pipeline orchestrator
```

## Prompts Are The Interface

Designers control output by editing files in `generated/prompts/`. The scripts read these prompts and combine them with reference images before sending to Gemini.

**Image order in API calls:**
1. Space photos (annotated) - "this is where we are"
2. Inspiration references - "this is what we want"
3. Layout drawings (if available) - "this is the spatial plan"
4. Text prompt - "combine the above into this design"

## Critical Rules

1. **Always send space photos** - Gemini must know the actual garden dimensions/shape
2. **Annotate first** - Labeled photos produce much better results than raw photos
3. **Verify against space** - Every generated image must match the real garden proportions
4. **Rejected != deleted** - Rejected images go to `generated/rejected/` for review
5. **Prompts are markdown** - Edit them freely, the scripts load them as text
