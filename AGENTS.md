# Evelien Garden - AI Agent Instructions

## Project Overview

AI-powered garden design visualization using Gemini (nano-banana-pro-preview) to generate consistent garden shade, seating, planting, and play area designs based on reference photos and inspiration images.

## Tech Stack

| Component | Technology |
|-----------|------------|
| AI Model | Gemini nano-banana-pro-preview |
| Language | Python 3.x |
| Dependencies | google-genai, pillow, python-dotenv |

## Pipeline: Annotate -> Generate -> Verify (Self-Healing)

```
1. ANNOTATE  (scripts/annotate.py)
   Send space photos to Gemini -> get labeled annotations
   (dimensions, sun direction, existing features, boundaries)

2. GENERATE  (scripts/generate.py)
   Send annotated photos + inspiration refs + layout drawings + prompts
   -> Gemini generates design visuals
   Accepts feedback from previous verification to self-correct

3. VERIFY    (scripts/verify.py)
   Send generated image + original space photo to Gemini
   -> Structured JSON scoring (5 criteria, 50 points max)
   -> Returns issues[] and prompt_adjustments[] for feedback loop

4. PIPELINE  (scripts/pipeline.py)
   Full cycle: annotate -> generate -> verify -> inject feedback -> retry
   Features: feedback passthrough, convergence detection, best-version tracking

5. STATUS    (scripts/status.py)
   Quick overview: photo counts, per-zone progress, best scores, readiness
```

## Key Commands

```bash
# Setup
cp .env.example .env  # Add your GEMINI_API_KEY
python -m venv venv && source venv/bin/activate
pip install google-genai pillow python-dotenv

# Check project status
python scripts/status.py

# Annotate space photos first
python scripts/annotate.py

# Generate designs for a zone
python scripts/generate.py --zone shade
python scripts/generate.py --zone seating --count 3

# Dry-run: see what would be sent to Gemini without API calls
python scripts/generate.py --zone shade --dry-run
python scripts/pipeline.py --zone shade --dry-run

# Full pipeline with self-healing feedback loop
python scripts/pipeline.py --zone shade --max-retries 5

# Verify a specific generated image
python scripts/verify.py --image generated/visuals/shade_v1.jpg
python scripts/verify.py --all
```

## Self-Healing Feedback Loop

The pipeline doesn't just retry blindly. On each attempt:

1. **Generate** design with zone prompt (+ feedback from previous attempt)
2. **Verify** against space photos -> structured JSON with scores and issues
3. **Extract** `prompt_adjustments` from verification (e.g., "reduce shade by 20%")
4. **Inject** adjustments into next generation prompt as `## ADJUSTMENT BASED ON PREVIOUS FEEDBACK`
5. **Convergence check**: if score doesn't improve for 2 consecutive attempts, stop early
6. **Summary**: reports all attempts with scores, highlights best version

## Verification Scoring (JSON)

Verify returns structured JSON with 5 criteria (1-10 each):
- `space_match` - Dimensions correct?
- `feature_preservation` - Existing features respected?
- `proportions` - Elements correctly sized?
- `feasibility` - Could this be built?
- `style_consistency` - Matches inspiration?

Thresholds: PASS (40+), MARGINAL (30-39), REJECT (<30)

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
│   │   ├── system_prompt.md  # Garden rules, material palette, colors
│   │   ├── annotate_prompt.md # How to annotate space photos
│   │   ├── shade.md          # Shade zone generation prompt
│   │   ├── seating.md        # Seating zone generation prompt
│   │   ├── plants.md         # Plants zone generation prompt
│   │   ├── play-area.md      # Play area generation prompt
│   │   ├── full.md           # Full garden generation prompt
│   │   └── verify_prompt.md  # JSON verification scoring rubric
│   ├── annotated/            # Annotated versions of space photos
│   ├── visuals/              # Final generated designs
│   ├── rejected/             # Failed verification (for review)
│   └── feedback/             # Generation logs & verify scores
│
└── scripts/                  # Python tools
    ├── annotate.py           # Step 1: Annotate reference photos
    ├── generate.py           # Step 2: Generate designs (+ feedback, dry-run)
    ├── verify.py             # Step 3: JSON verification scoring
    ├── pipeline.py           # Full pipeline with feedback loop
    └── status.py             # Project status report
```

## Prompts Are The Interface

Designers control output by editing files in `generated/prompts/`. The scripts read these prompts and combine them with reference images before sending to Gemini.

**Image order in API calls:**
1. Space photos (annotated) - "this is where we are"
2. Inspiration references - "this is what we want"
3. Layout drawings (if available) - "this is the spatial plan"
4. Text prompt - "combine the above into this design"

**Prompt features:**
- Material palette with specific timber/stone/fabric choices
- Color direction (earthy tones, no bright primaries)
- Cross-zone references (shade mentions seating, play-area mentions visibility)
- "Image 1 is AUTHORITATIVE" emphasis on every zone prompt
- Scoring rubric with concrete criteria per score band (1-3 poor, 4-6 acceptable, 7-8 good, 9-10 excellent)

## Critical Rules

1. **Always send space photos** - Gemini must know the actual garden dimensions/shape
2. **Annotate first** - Labeled photos produce much better results than raw photos
3. **Verify against space** - Every generated image must match the real garden proportions
4. **Rejected != deleted** - Rejected images go to `generated/rejected/` for review
5. **Prompts are markdown** - Edit them freely, the scripts load them as text
6. **Feedback loop** - Verification issues automatically feed into next generation attempt
