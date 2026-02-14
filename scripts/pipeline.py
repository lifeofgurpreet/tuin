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
import time
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
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without calling API")
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

    # Step 2 + 3: Generate + Verify loop with feedback passthrough
    attempts = []  # [(path, score, verdict), ...]
    feedback = ""

    for attempt in range(1, args.max_retries + 1):
        print(f"\n{'='*60}")
        print(f"  ATTEMPT {attempt}/{args.max_retries} - {args.zone}")
        print(f"{'='*60}")

        if feedback:
            print(f"  [FEEDBACK] Injecting corrections from previous attempt")

        # Generate
        print(f"\n  --- GENERATE ---")
        result_path = generate(client, args.zone, feedback=feedback, dry_run=args.dry_run)

        if args.dry_run:
            print("\n[DRY RUN] Pipeline would continue with verify step")
            return

        if not result_path:
            print(f"[ERROR] Generation failed on attempt {attempt}")
            if attempt < args.max_retries:
                time.sleep(2)
                continue
            else:
                print("Max retries reached. Check your prompts and references.")
                break

        # Verify
        print(f"\n  --- VERIFY ---")
        verdict = verify_image(client, result_path)
        final_verdict = handle_verdict(result_path, verdict)
        score = verdict.get("total", 0)
        attempts.append((result_path, score, final_verdict))

        if final_verdict == "PASS":
            print(f"\n{'='*60}")
            print(f"  PIPELINE COMPLETE - {args.zone}")
            print(f"  Result: {result_path.name}")
            print(f"  Score: {score}/50")
            print(f"{'='*60}")
            return

        # Build feedback for next attempt from verification
        feedback_parts = []
        if verdict.get("prompt_adjustments"):
            feedback_parts.extend(verdict["prompt_adjustments"])
        if verdict.get("issues"):
            feedback_parts.append("Issues to fix: " + "; ".join(verdict["issues"]))
        if verdict.get("feedback") and not verdict.get("prompt_adjustments"):
            feedback_parts.append(verdict["feedback"])
        feedback = "\n".join(feedback_parts) if feedback_parts else verdict.get("feedback", "")

        # Convergence detection: if score hasn't improved for 2 consecutive attempts
        if len(attempts) >= 2:
            prev_score = attempts[-2][1]
            if score <= prev_score:
                # Check if 2 consecutive non-improvements
                if len(attempts) >= 3:
                    prev_prev_score = attempts[-3][1]
                    if prev_score <= prev_prev_score:
                        print(f"\n[CONVERGED] Score not improving: {prev_prev_score} -> {prev_score} -> {score}")
                        print(f"Stopping early.")
                        break

        if final_verdict == "MARGINAL":
            print(f"\n[WARN] Marginal result ({score}/50)")
            if attempt < args.max_retries:
                print(f"Trying for better with feedback injection...")
                time.sleep(2)
                continue
            # Last attempt - will fall through to summary

        if final_verdict == "REJECT":
            print(f"\n[REJECT] Score {score}/50")
            if attempt < args.max_retries:
                print(f"Retrying with feedback...")
                time.sleep(2)
            else:
                print(f"\nAll {args.max_retries} attempts exhausted.")

    # Summary: report best version
    if attempts:
        best = max(attempts, key=lambda x: x[1])
        best_path, best_score, best_verdict = best
        print(f"\n{'='*60}")
        print(f"  PIPELINE SUMMARY - {args.zone}")
        print(f"  Attempts: {len(attempts)}")
        for i, (p, s, v) in enumerate(attempts, 1):
            marker = " <-- BEST" if (p, s, v) == best else ""
            name = p.name if p.exists() else f"{p.name} (moved to rejected)"
            print(f"    #{i}: {name} - {s}/50 [{v}]{marker}")
        print(f"  Best: {best_path.name} ({best_score}/50)")
        print(f"{'='*60}")
    else:
        print("\n[ERROR] No successful generations. Check prompts and references.")


if __name__ == "__main__":
    main()
