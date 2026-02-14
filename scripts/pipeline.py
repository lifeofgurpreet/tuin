"""
EVELIEN GARDEN - FULL PIPELINE
================================

Orchestrates the complete flow:
  1. Annotate space photos (if not already done)
  2. Generate design for a zone
  3. Verify against space photos
  4. If rejected, retry with feedback adjustments (self-healing loop)

Usage:
    python scripts/pipeline.py --zone shade
    python scripts/pipeline.py --zone shade --max-retries 3
    python scripts/pipeline.py --zone full --skip-annotate
"""

import argparse
import sys
from pathlib import Path

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from annotate import annotate_photo, load_image, SPACE_DIR, ANNOTATED_DIR
from generate import generate, ZONES, VISUALS_DIR
from verify import verify_image, handle_verdict

import os
from google import genai

PROJECT_ROOT = Path(__file__).parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not set. Copy .env.example to .env and add your key."
    )


def has_annotated_photos() -> bool:
    """Check if we already have annotated photos."""
    if not ANNOTATED_DIR.exists():
        return False
    annotated = (
        list(ANNOTATED_DIR.glob("*_annotated.jpg"))
        + list(ANNOTATED_DIR.glob("*_notes.md"))
    )
    return len(annotated) > 0


def run_annotation(client: genai.Client) -> int:
    """Annotate all space photos. Returns count of annotated."""
    if not SPACE_DIR.exists():
        print("[ERROR] No space photos in ref/space/")
        print("Add garden photos first, then run the pipeline.")
        return 0

    photos = (
        list(SPACE_DIR.glob("*.jpg"))
        + list(SPACE_DIR.glob("*.jpeg"))
        + list(SPACE_DIR.glob("*.png"))
    )

    if not photos:
        print("[ERROR] No photos found in ref/space/")
        return 0

    count = 0
    for photo in sorted(photos):
        result = annotate_photo(client, photo)
        if result:
            count += 1

    return count


def main():
    parser = argparse.ArgumentParser(description="Full garden design pipeline")
    parser.add_argument(
        "--zone",
        required=True,
        choices=ZONES,
        help="Zone to generate",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries on verification failure (default: 3)",
    )
    parser.add_argument(
        "--skip-annotate",
        action="store_true",
        help="Skip annotation step (if already done)",
    )
    args = parser.parse_args()

    client = genai.Client(api_key=API_KEY)

    # Step 1: Annotate (if needed)
    if not args.skip_annotate and not has_annotated_photos():
        print("\n" + "=" * 60)
        print("  STEP 1: ANNOTATING SPACE PHOTOS")
        print("=" * 60)
        count = run_annotation(client)
        if count == 0:
            print("\n[WARN] No photos annotated. Continuing with raw photos...")
    elif has_annotated_photos():
        print("[OK] Annotated photos already exist, skipping annotation")
    else:
        print("[OK] Skipping annotation (--skip-annotate)")

    # Step 2 + 3: Generate + Verify loop
    for attempt in range(1, args.max_retries + 1):
        print(f"\n{'='*60}")
        print(f"  STEP 2: GENERATE (attempt {attempt}/{args.max_retries})")
        print(f"{'='*60}")

        result_path = generate(client, args.zone)
        if not result_path:
            print(f"[ERROR] Generation failed on attempt {attempt}")
            if attempt < args.max_retries:
                print("Retrying...")
                continue
            else:
                print("Max retries reached. Check your prompts and references.")
                return

        print(f"\n{'='*60}")
        print(f"  STEP 3: VERIFY")
        print(f"{'='*60}")

        verdict = verify_image(client, result_path)
        final_verdict = handle_verdict(result_path, verdict)

        if final_verdict == "PASS":
            print(f"\n{'='*60}")
            print(f"  PIPELINE COMPLETE - {args.zone}")
            print(f"  Result: {result_path.name}")
            print(f"  Score: {verdict['total']}/50")
            print(f"{'='*60}")
            return

        if final_verdict == "MARGINAL":
            print(f"\n[WARN] Marginal result ({verdict['total']}/50)")
            print(f"Keeping image but trying for better on next attempt...")
            # Don't reject marginal - keep it, but try again
            if attempt < args.max_retries:
                continue
            else:
                print(f"\nBest result after {args.max_retries} attempts: {result_path.name}")
                return

        # REJECT
        print(f"\n[REJECT] Score {verdict['total']}/50")
        if verdict["feedback"]:
            print(f"Feedback: {verdict['feedback'][:300]}")
        if attempt < args.max_retries:
            print(f"Retrying ({attempt + 1}/{args.max_retries})...")
        else:
            print(f"\nAll {args.max_retries} attempts rejected. Review prompts and references.")

    print("\nPipeline finished. Check generated/visuals/ and generated/rejected/")


if __name__ == "__main__":
    main()
