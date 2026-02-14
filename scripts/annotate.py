"""
EVELIEN GARDEN - ANNOTATE SPACE PHOTOS
========================================

Sends garden space photos to Gemini nano-banana-pro-preview and asks it
to return annotated versions with labels for dimensions, features, sun
direction, boundaries, etc.

Usage:
    python scripts/annotate.py
    python scripts/annotate.py --photo ref/space/garden_north.jpg
"""

import argparse
import io
import re
import time
from pathlib import Path
from datetime import datetime

from google import genai
from google.genai import types
from PIL import Image

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

import os

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not set. Copy .env.example to .env and add your key."
    )

MODEL = "nano-banana-pro-preview"
SPACE_DIR = PROJECT_ROOT / "ref" / "space"
OUTPUT_DIR = PROJECT_ROOT / "generated" / "annotated"
ANNOTATED_DIR = OUTPUT_DIR  # alias used by pipeline.py


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


def load_prompt(name: str) -> str:
    path = PROJECT_ROOT / "generated" / "prompts" / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def annotate_photo(client: genai.Client, photo_path: Path) -> Path | None:
    """Send a space photo to Gemini for annotation."""
    print(f"\n[*] Annotating: {photo_path.name}")

    img = load_image(photo_path)
    prompt = load_prompt("annotate_prompt")
    if not prompt:
        print("[ERROR] No annotate_prompt.md found in generated/prompts/")
        return None

    contents = [
        types.Part.from_bytes(
            data=image_to_bytes(img),
            mime_type="image/jpeg",
        ),
        prompt,
    ]

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                temperature=0.4,
            ),
        )

        # Safe access to response
        try:
            parts = response.candidates[0].content.parts
        except (IndexError, AttributeError):
            text = getattr(response, 'text', '') or str(response)
            print(f"[WARN] No valid response from Gemini. Response: {text[:300]}")
            return None

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stem = photo_path.stem
        text_parts = []

        for part in parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                output_path = OUTPUT_DIR / f"{stem}_annotated.jpg"
                out_img = Image.open(io.BytesIO(part.inline_data.data))
                if out_img.mode in ("RGBA", "P"):
                    out_img = out_img.convert("RGB")
                out_img.save(str(output_path), "JPEG", quality=95)
                print(f"[OK] Saved annotated image: {output_path.name}")
                return output_path
            elif part.text:
                text_parts.append(part.text)

        # If no image returned, save text response as notes
        if text_parts:
            notes_path = OUTPUT_DIR / f"{stem}_notes.md"
            notes_path.write_text(
                f"# Annotation Notes: {photo_path.name}\n\n"
                f"Generated: {datetime.now().isoformat()}\n\n"
                + "\n".join(text_parts),
                encoding="utf-8",
            )
            print(f"[INFO] No image returned, saved text notes: {notes_path.name}")

        return None

    except Exception as e:
        print(f"[ERROR] Annotation failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Annotate garden space photos")
    parser.add_argument("--photo", type=str, help="Specific photo to annotate")
    args = parser.parse_args()

    client = genai.Client(api_key=API_KEY)

    if args.photo:
        photo_path = Path(args.photo)
        if not photo_path.is_absolute():
            photo_path = PROJECT_ROOT / photo_path
        if not photo_path.exists():
            print(f"[ERROR] Photo not found: {photo_path}")
            return
        annotate_photo(client, photo_path)
    else:
        # Annotate all space photos
        if not SPACE_DIR.exists():
            print(f"[ERROR] No space photos directory: {SPACE_DIR}")
            print("Add garden photos to ref/space/ first.")
            return

        photos = (
            list(SPACE_DIR.glob("*.jpg"))
            + list(SPACE_DIR.glob("*.jpeg"))
            + list(SPACE_DIR.glob("*.png"))
            + list(SPACE_DIR.glob("*.heif"))
            + list(SPACE_DIR.glob("*.heic"))
        )

        if not photos:
            print("[ERROR] No photos found in ref/space/")
            print("Add garden photos (.jpg, .png, .heif) to ref/space/ first.")
            return

        print(f"[*] Found {len(photos)} space photos to annotate")
        results = []
        for photo in sorted(photos):
            result = annotate_photo(client, photo)
            if result:
                results.append(result)

        print(f"\n{'='*50}")
        print(f"Annotated {len(results)}/{len(photos)} photos")
        print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
