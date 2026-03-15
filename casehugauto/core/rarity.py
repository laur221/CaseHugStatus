import math
import re
from typing import Optional


# Canonical CS rarity tiers and representative colors.
RARITY_TIERS = [
    ("Consumer Grade (White)", "#B0C3D9"),
    ("Industrial Grade (Light Blue)", "#5E98D9"),
    ("Mil-Spec (Blue)", "#4B69FF"),
    ("Restricted (Purple)", "#8847FF"),
    ("Classified (Pink)", "#D32CE6"),
    ("Covert (Red)", "#EB4B4B"),
    ("Extraordinary (Gold)", "#FFD700"),
    ("Contraband (Orange)", "#CF6A32"),
]


def _parse_hex_color(value: str) -> Optional[tuple[int, int, int]]:
    if not value:
        return None
    m = re.search(r"#([0-9a-fA-F]{6})", value.strip())
    if not m:
        return None
    raw = m.group(1)
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def rarity_from_color(color_hex: Optional[str]) -> Optional[str]:
    """
    Infer rarity from a color hex by nearest canonical CS rarity color.
    Returns a label like: "Mil-Spec (Blue)".
    """
    if not color_hex:
        return "Unknown"

    source = _parse_hex_color(color_hex)
    if source is None:
        return "Unknown"

    best_label = None
    best_distance = None
    sr, sg, sb = source

    for label, canonical_hex in RARITY_TIERS:
        target = _parse_hex_color(canonical_hex)
        if target is None:
            continue
        tr, tg, tb = target
        distance = math.sqrt((sr - tr) ** 2 + (sg - tg) ** 2 + (sb - tb) ** 2)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_label = label

    return best_label or "Unknown"


def color_for_rarity_label(rarity: Optional[str]) -> str:
    if not rarity:
        return "#A3A7BB"

    rarity_lower = rarity.lower()
    for label, color in RARITY_TIERS:
        if label.lower() == rarity_lower:
            return color

    # Prefix fallback (in case label gets reformatted).
    for label, color in RARITY_TIERS:
        if rarity_lower.startswith(label.split("(", 1)[0].strip().lower()):
            return color

    return "#A3A7BB"
