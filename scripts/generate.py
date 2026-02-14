"""
EVELIEN GARDEN - GENERATE DESIGNS
===================================

Generates garden design visuals by sending:
1. Annotated space photos (the actual garden)
2. Inspiration references (what we want it to look like)
3. Layout drawings (top-down spatial plan, if available)
4. Text prompt (zone-specific instructions)

Usage:
    python scripts/generate.py --zone shade
    python scripts/generate.py --zone seating
    python scripts/generate.py --zone play-area
    python scripts/generate.py --zone plants
    python scripts/generate.py --zone full
"""

import argparse
import io
import os
import random
import re
from datetime import datetime
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

# Directories
REF_SPACE = PROJECT_ROOT / "ref" / "space"
REF_INSPIRATION = PROJECT_ROOT / "ref" / "inspiration"
DRAWINGS_DIR = PROJECT_ROOT / "drawings" / "layouts"
ANNOTATED_DIR = PROJECT_ROOT / "generated" / "annotated"
VISUALS_DIR = PROJECT_ROOT / "generated" / "visuals"
PROMPTS_DIR = PROJECT_ROOT / "generated" / "prompts"
FEEDBACK_DIR = PROJECT_ROOT / "generated" / "feedback"

ZONES = ["shade", "seating", "plants", "play-area", "full"]


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
    path = PROMPTS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def get_images(directory: Path, max_count: int = 3) -> list[Path]:
    """Get image files from a directory."""
    if not directory.exists():
        return []
    images = (
        list(directory.glob("*.jpg"))
        + list(directory.glob("*.jpeg"))
        + list(directory.glob("*.png"))
    )
    if len(images) > max_count:
        images = random.sample(images, max_count)
    return sorted(images)


def get_next_version(zone: str) -> int:
    """Get next version number for a zone."""
    existing = list(VISUALS_DIR.glob(f"{zone}_v*.jpg"))
    if not existing:
        return 1
    numbers = []
    for f in existing:
        match = re.search(r"_v(\d+)", f.stem)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers) + 1 if numbers else 1


def generate(client: genai.Client, zone: str) -> Path | None:
    """Generate a design visual for a zone."""
    if zone not in ZONES:
        print(f"[ERROR] Unknown zone: {zone}. Choose from: {', '.join(ZONES)}")
        return None

    print(f"\n{'='*60}")
    print(f"  GENERATING: {zone}")
    print(f"{'='*60}")

    # Build contents list - images first, prompt last
    contents = []

    # 1. Annotated space photos (most important - grounds the design in reality)
    annotated = get_images(ANNOTATED_DIR, max_count=3)
    if not annotated:
        # Fall back to raw space photos
        annotated = get_images(REF_SPACE, max_count=3)
        if annotated:
            print(f"[WARN] No annotated photos found, using raw space photos")
        else:
            print(f"[WARN] No space photos at all - generation may not match your garden")

    for photo in annotated:
        img = load_image(photo)
        contents.append(
            types.Part.from_bytes(
                data=image_to_bytes(img, max_size=1200),
                mime_type="image/jpeg",
            )
        )
        print(f"    [OK] Space: {photo.name}")

    # 2. Inspiration references for this zone
    inspiration_dir = REF_INSPIRATION / zone
    if zone == "full":
        # For full garden, sample from all inspiration subdirs
        all_inspiration = []
        for subdir in REF_INSPIRATION.iterdir():
            if subdir.is_dir():
                all_inspiration.extend(get_images(subdir, max_count=1))
        inspiration = all_inspiration[:4]
    else:
        inspiration = get_images(inspiration_dir, max_count=3)

    for ref in inspiration:
        img = load_image(ref)
        contents.append(
            types.Part.from_bytes(
                data=image_to_bytes(img, max_size=1000),
                mime_type="image/jpeg",
            )
        )
        print(f"    [OK] Inspiration: {ref.name}")

    if not inspiration:
        print(f"    [WARN] No inspiration images in ref/inspiration/{zone}/")

    # 3. Layout drawings (if available)
    layouts = get_images(DRAWINGS_DIR, max_count=1)
    for layout in layouts:
        img = load_image(layout)
        contents.append(
            types.Part.from_bytes(
                data=image_to_bytes(img, max_size=1200),
                mime_type="image/jpeg",
            )
        )
        print(f"    [OK] Layout: {layout.name}")

    # 4. Build text prompt
    system = load_prompt("system_prompt")
    zone_prompt = load_prompt(zone)
    if not zone_prompt:
        print(f"[ERROR] No prompt found: generated/prompts/{zone}.md")
        return None

    # Also load annotation notes if they exist
    notes = []
    for notes_file in ANNOTATED_DIR.glob("*_notes.md"):
        notes.append(notes_file.read_text(encoding="utf-8"))

    prompt_parts = []
    if system:
        prompt_parts.append("=== GARDEN RULES ===\n" + system)
    if notes:
        prompt_parts.append("=== SPACE ANNOTATIONS ===\n" + "\n---\n".join(notes))
    prompt_parts.append("=== GENERATION TASK ===\n" + zone_prompt)

    full_prompt = "\n\n".join(prompt_parts)
    contents.append(full_prompt)
    print(f"    [OK] Prompt: {len(full_prompt)} chars")

    if not any(
        isinstance(c, types.Part) and c.inline_data for c in contents
        if isinstance(c, types.Part)
    ):
        print("[WARN] No images being sent. Results will be generic.")

    # Generate
    print(f"\n[*] Calling nano-banana-pro-preview...")
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                temperature=0.7,
            ),
        )

        VISUALS_DIR.mkdir(parents=True, exist_ok=True)
        version = get_next_version(zone)
        text_parts = []

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                output_path = VISUALS_DIR / f"{zone}_v{version}.jpg"
                out_img = Image.open(io.BytesIO(part.inline_data.data))
                if out_img.mode in ("RGBA", "P"):
                    out_img = out_img.convert("RGB")
                out_img.save(str(output_path), "JPEG", quality=95)
                print(f"\n[OK] Saved: {output_path.name}")

                # Log generation
                FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
                log_path = FEEDBACK_DIR / "generation_log.md"
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(
                        f"\n## {zone}_v{version} - {datetime.now().isoformat()}\n"
                        f"- Zone: {zone}\n"
                        f"- Space photos: {len(annotated)}\n"
                        f"- Inspiration refs: {len(inspiration)}\n"
                        f"- Layout drawings: {len(layouts)}\n"
                    )

                return output_path
            elif part.text:
                text_parts.append(part.text)

        if text_parts:
            print("[INFO] No image returned. Text response:")
            print("\n".join(text_parts[:500]))

        return None

    except Exception as e:
        print(f"[ERROR] Generation failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Generate garden design visuals")
    parser.add_argument(
        "--zone",
        required=True,
        choices=ZONES,
        help="Zone to generate",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of variations to generate (default: 1)",
    )
    args = parser.parse_args()

    client = genai.Client(api_key=API_KEY)

    results = []
    for i in range(args.count):
        if args.count > 1:
            print(f"\n--- Variation {i + 1}/{args.count} ---")
        result = generate(client, args.zone)
        if result:
            results.append(result)

    print(f"\n{'='*50}")
    print(f"Generated {len(results)}/{args.count} visuals for zone: {args.zone}")
    print(f"Output: {VISUALS_DIR}")


if __name__ == "__main__":
    main()
