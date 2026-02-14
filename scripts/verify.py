"""
EVELIEN GARDEN - VERIFY GENERATED DESIGNS (Self-Healing Loop)
===============================================================

Compares generated design images against original space photos to check
that the design actually matches the real garden. Rejects images that
don't respect the space dimensions, existing features, or proportions.

Usage:
    python scripts/verify.py --image generated/visuals/shade_v1.jpg
    python scripts/verify.py --all
"""

import argparse
import io
import json
import os
import re
import shutil
import time
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image

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

MODEL = "nano-banana-pro-preview"

REF_SPACE = PROJECT_ROOT / "ref" / "space"
ANNOTATED_DIR = PROJECT_ROOT / "generated" / "annotated"
VISUALS_DIR = PROJECT_ROOT / "generated" / "visuals"
REJECTED_DIR = PROJECT_ROOT / "generated" / "rejected"
FEEDBACK_DIR = PROJECT_ROOT / "generated" / "feedback"
PROMPTS_DIR = PROJECT_ROOT / "generated" / "prompts"

PASS_THRESHOLD = 40  # out of 50
MARGINAL_THRESHOLD = 30


def load_image(path: Path) -> Image.Image:
    img = Image.open(str(path))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    return img


def image_to_bytes(img: Image.Image, max_size: int = 1500) -> bytes:
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def get_images(directory: Path, max_count: int = 3) -> list[Path]:
    if not directory.exists():
        return []
    images = (
        list(directory.glob("*.jpg"))
        + list(directory.glob("*.jpeg"))
        + list(directory.glob("*.png"))
    )
    return sorted(images)[:max_count]


def parse_verdict(text: str) -> dict:
    """Parse verification response. Tries JSON first, falls back to regex."""
    result = {"verdict": "UNKNOWN", "total": 0, "feedback": "", "issues": [], "prompt_adjustments": [], "raw": text}

    # Try JSON parsing first
    json_match = re.search(r'\{[\s\S]*"total"[\s\S]*\}', text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            result["total"] = int(data.get("total", 0))
            verdict = data.get("verdict", "").upper()
            if verdict in ("PASS", "MARGINAL", "REJECT"):
                result["verdict"] = verdict
            result["issues"] = data.get("issues", [])
            result["prompt_adjustments"] = data.get("prompt_adjustments", [])
            # Build feedback from issues + adjustments
            parts = []
            if result["issues"]:
                parts.append("Issues: " + "; ".join(result["issues"]))
            if result["prompt_adjustments"]:
                parts.append("Adjustments: " + "; ".join(result["prompt_adjustments"]))
            result["feedback"] = " | ".join(parts) if parts else ""
            # Derive verdict from score if not explicit
            if result["verdict"] == "UNKNOWN" and result["total"] > 0:
                if result["total"] >= PASS_THRESHOLD:
                    result["verdict"] = "PASS"
                elif result["total"] >= MARGINAL_THRESHOLD:
                    result["verdict"] = "MARGINAL"
                else:
                    result["verdict"] = "REJECT"
            return result
        except (json.JSONDecodeError, ValueError, KeyError):
            pass  # Fall through to regex

    # Regex fallback (existing logic)
    total_match = re.search(r"TOTAL:\s*(\d+)/50", text)
    if total_match:
        result["total"] = int(total_match.group(1))

    verdict_match = re.search(r"VERDICT:\s*(PASS|MARGINAL|REJECT)", text, re.IGNORECASE)
    if verdict_match:
        result["verdict"] = verdict_match.group(1).upper()
    elif result["total"] >= PASS_THRESHOLD:
        result["verdict"] = "PASS"
    elif result["total"] >= MARGINAL_THRESHOLD:
        result["verdict"] = "MARGINAL"
    elif result["total"] > 0:
        result["verdict"] = "REJECT"

    feedback_match = re.search(r"FEEDBACK:\s*(.+)", text, re.DOTALL)
    if feedback_match:
        result["feedback"] = feedback_match.group(1).strip()

    return result


def verify_image(client: genai.Client, image_path: Path) -> dict:
    """Verify a generated image against space photos."""
    print(f"\n[*] Verifying: {image_path.name}")

    # Load the generated image
    gen_img = load_image(image_path)

    # Load space reference photos (annotated preferred, raw fallback)
    space_photos = get_images(ANNOTATED_DIR, max_count=2)
    if not space_photos:
        space_photos = get_images(REF_SPACE, max_count=2)

    if not space_photos:
        print("[WARN] No space photos to verify against - skipping verification")
        return {"verdict": "PASS", "total": 50, "feedback": "No reference to verify against", "raw": ""}

    # Load verify prompt
    verify_prompt = (PROMPTS_DIR / "verify_prompt.md").read_text(encoding="utf-8") if (PROMPTS_DIR / "verify_prompt.md").exists() else ""

    # Build contents: space photos first, then generated image, then prompt
    contents = []

    for photo in space_photos:
        img = load_image(photo)
        contents.append(
            types.Part.from_bytes(
                data=image_to_bytes(img, max_size=1200),
                mime_type="image/jpeg",
            )
        )
        print(f"    [REF] {photo.name}")

    # Generated image
    contents.append(
        types.Part.from_bytes(
            data=image_to_bytes(gen_img, max_size=1200),
            mime_type="image/jpeg",
        )
    )
    print(f"    [GEN] {image_path.name}")

    prompt = (
        "The first image(s) are PHOTOS of the actual garden space. "
        "The last image is a GENERATED design for this garden. "
        "Compare them and evaluate:\n\n" + verify_prompt
    )
    contents.append(prompt)

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT"],
                temperature=0.3,  # Low temp for consistent scoring
            ),
        )

        # Safe access to response
        try:
            parts = response.candidates[0].content.parts
        except (IndexError, AttributeError):
            text = getattr(response, 'text', '') or str(response)
            print(f"[WARN] No valid response from Gemini: {text[:200]}")
            return {"verdict": "UNKNOWN", "total": 0, "feedback": "No valid response from Gemini", "issues": [], "prompt_adjustments": [], "raw": text}

        response_text = ""
        for part in parts:
            if part.text:
                response_text += part.text

        result = parse_verdict(response_text)

        # Print result
        verdict_emoji = {"PASS": "[PASS]", "MARGINAL": "[WARN]", "REJECT": "[FAIL]"}
        print(f"\n    {verdict_emoji.get(result['verdict'], '[???]')} Score: {result['total']}/50 - {result['verdict']}")
        if result["feedback"]:
            print(f"    Feedback: {result['feedback'][:200]}")

        return result

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        return {"verdict": "UNKNOWN", "total": 0, "feedback": str(e), "issues": [], "prompt_adjustments": [], "raw": ""}


def handle_verdict(image_path: Path, result: dict) -> str:
    """Move rejected images and log feedback."""
    if result["verdict"] == "REJECT":
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        rejected_path = REJECTED_DIR / image_path.name
        shutil.move(str(image_path), str(rejected_path))
        print(f"    [MOVED] {image_path.name} -> rejected/")

    # Log feedback
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    log_path = FEEDBACK_DIR / "verify_log.md"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n## {image_path.name} - {result['verdict']}\n")
        f.write(f"- Score: {result['total']}/50\n")
        if result.get("issues"):
            f.write(f"- Issues: {', '.join(result['issues'])}\n")
        if result.get("prompt_adjustments"):
            f.write(f"- Adjustments: {', '.join(result['prompt_adjustments'])}\n")
        if result["feedback"]:
            f.write(f"- Feedback: {result['feedback']}\n")
        f.write(f"- Raw:\n```\n{result['raw'][:500]}\n```\n")

    return result["verdict"]


def main():
    parser = argparse.ArgumentParser(description="Verify generated designs against space photos")
    parser.add_argument("--image", type=str, help="Specific image to verify")
    parser.add_argument("--all", action="store_true", help="Verify all generated visuals")
    args = parser.parse_args()

    client = genai.Client(api_key=API_KEY)

    if args.image:
        image_path = Path(args.image)
        if not image_path.is_absolute():
            image_path = PROJECT_ROOT / image_path
        if not image_path.exists():
            print(f"[ERROR] Image not found: {image_path}")
            return
        result = verify_image(client, image_path)
        handle_verdict(image_path, result)

    elif args.all:
        images = get_images(VISUALS_DIR, max_count=100)
        if not images:
            print("[ERROR] No images in generated/visuals/")
            return

        stats = {"PASS": 0, "MARGINAL": 0, "REJECT": 0, "UNKNOWN": 0}
        for img_path in images:
            result = verify_image(client, img_path)
            verdict = handle_verdict(img_path, result)
            stats[verdict] = stats.get(verdict, 0) + 1

        print(f"\n{'='*50}")
        print(f"Verification complete:")
        for k, v in stats.items():
            if v > 0:
                print(f"  {k}: {v}")

    else:
        print("Specify --image <path> or --all")


if __name__ == "__main__":
    main()
