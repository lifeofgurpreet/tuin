"""
EVELIEN GARDEN - STATUS
========================

Scans generated/ directories and reports pipeline status:
- Space photo counts
- Annotated photo counts
- Per-zone: generated versions, best scores, rejected count

Usage:
    python scripts/status.py
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

REF_SPACE = PROJECT_ROOT / "ref" / "space"
REF_INSPIRATION = PROJECT_ROOT / "ref" / "inspiration"
DRAWINGS_DIR = PROJECT_ROOT / "drawings" / "layouts"
ANNOTATED_DIR = PROJECT_ROOT / "generated" / "annotated"
VISUALS_DIR = PROJECT_ROOT / "generated" / "visuals"
REJECTED_DIR = PROJECT_ROOT / "generated" / "rejected"
FEEDBACK_DIR = PROJECT_ROOT / "generated" / "feedback"

ZONES = ["shade", "seating", "plants", "play-area", "full"]

IMAGE_GLOBS = ["*.jpg", "*.jpeg", "*.png"]


def count_images(directory: Path) -> int:
    if not directory.exists():
        return 0
    count = 0
    for glob in IMAGE_GLOBS:
        count += len(list(directory.glob(glob)))
    return count


def get_zone_images(directory: Path, zone: str) -> list[Path]:
    if not directory.exists():
        return []
    images = []
    for glob in IMAGE_GLOBS:
        images.extend(directory.glob(f"{zone}_v*{glob[1:]}"))
    return sorted(images)


def parse_verify_log() -> dict[str, list[dict]]:
    """Parse verify_log.md to extract scores per image."""
    log_path = FEEDBACK_DIR / "verify_log.md"
    if not log_path.exists():
        return {}

    results = {}
    text = log_path.read_text(encoding="utf-8")

    # Parse entries like: ## shade_v1.jpg - PASS\n- Score: 42/50
    for block in text.split("\n## ")[1:]:
        lines = block.strip().split("\n")
        if not lines:
            continue
        header = lines[0]
        # Extract filename and verdict
        match = re.match(r"(\S+)\s*-\s*(PASS|MARGINAL|REJECT|UNKNOWN)", header)
        if not match:
            continue
        filename = match.group(1)
        verdict = match.group(2)

        # Extract score
        score = 0
        for line in lines[1:]:
            score_match = re.search(r"Score:\s*(\d+)/50", line)
            if score_match:
                score = int(score_match.group(1))
                break

        # Determine zone from filename
        zone = None
        for z in ZONES:
            if filename.startswith(z + "_"):
                zone = z
                break

        if zone:
            results.setdefault(zone, []).append({
                "filename": filename,
                "score": score,
                "verdict": verdict,
            })

    return results


def main():
    # Counts
    space_count = count_images(REF_SPACE)
    annotated_count = count_images(ANNOTATED_DIR)
    layout_count = count_images(DRAWINGS_DIR)

    # Inspiration per zone
    inspiration_counts = {}
    for zone in ZONES:
        if zone == "full":
            inspiration_counts[zone] = sum(
                count_images(REF_INSPIRATION / z) for z in ZONES if z != "full"
            )
        else:
            inspiration_counts[zone] = count_images(REF_INSPIRATION / zone)

    # Verify log data
    verify_data = parse_verify_log()

    # Print report
    print(f"\n{'='*55}")
    print(f"  EVELIEN GARDEN STATUS")
    print(f"{'='*55}")
    print(f"  Space photos:     {space_count}")
    print(f"  Annotated:        {annotated_count}")
    print(f"  Layouts:          {layout_count}")
    print()

    # Per-zone table
    header = f"  {'Zone':<12} {'Inspo':>5} {'Generated':>10} {'Best Score':>11} {'Rejected':>9}"
    print(header)
    print(f"  {'-'*12} {'-'*5} {'-'*10} {'-'*11} {'-'*9}")

    for zone in ZONES:
        generated = get_zone_images(VISUALS_DIR, zone)
        rejected = get_zone_images(REJECTED_DIR, zone)
        inspo = inspiration_counts.get(zone, 0)

        # Best score from verify log
        zone_results = verify_data.get(zone, [])
        if zone_results:
            best = max(zone_results, key=lambda x: x["score"])
            best_str = f"{best['score']}/50"
        else:
            best_str = "-"

        print(f"  {zone:<12} {inspo:>5} {len(generated):>10} {best_str:>11} {len(rejected):>9}")

    print(f"\n{'='*55}")

    # Readiness check
    issues = []
    if space_count == 0:
        issues.append("No space photos in ref/space/")
    if annotated_count == 0 and space_count > 0:
        issues.append("Space photos not annotated yet (run: python scripts/annotate.py)")

    total_inspiration = sum(inspiration_counts.values())
    if total_inspiration == 0:
        issues.append("No inspiration images in ref/inspiration/")

    if issues:
        print(f"\n  Readiness issues:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print(f"\n  Ready to generate!")

    print()


if __name__ == "__main__":
    main()
