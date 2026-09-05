#!/usr/bin/env python3
"""Scrape Abiotic Factor item pages ({{item}} infobox) from three categories:
Weapons_and_Ammo -> weapons.json, Food_and_Cooking -> food.json,
Armor_and_Gear -> armor.json. Pages are fetched once and routed by their
`category` field (more reliable than category membership alone).
"""
import json
import time

from shared import (
    OUT_DIR, get_wikitext, category_members, infobox_field, best_summary,
    clean_html, LANG_SUFFIX,
)

CATEGORIES = {
    "Weapons and Ammo": OUT_DIR / "weapons.json",
    "Food and Cooking": OUT_DIR / "food.json",
    "Armor and Gear": OUT_DIR / "armor.json",
}


def parse_item(title: str, wt: str) -> dict | None:
    if not wt or "{{item" not in wt.lower():
        return None
    it = {
        "name": title,
        "slug": title.replace(" ", "_").lstrip("."),
        "description": clean_html(infobox_field(wt, "description")),
        "flavor": clean_html(infobox_field(wt, "flavorText")),
        "category": infobox_field(wt, "category"),
        "weight": infobox_field(wt, "weight"),
        "stack": infobox_field(wt, "stackSize"),
        "tier": infobox_field(wt, "tier"),
        "durability": infobox_field(wt, "durability"),
        # weapon fields
        "weaponType": infobox_field(wt, "weaponType"),
        "weaponDamage": infobox_field(wt, "weaponDamage"),
        "weaponDamageType": infobox_field(wt, "weaponDamageType"),
        # food fields
        "hunger": infobox_field(wt, "consumableHungerFill"),
        "thirst": infobox_field(wt, "consumableThirstFill"),
        "sanity": infobox_field(wt, "consumableSanityFill"),
        "cookingStage": infobox_field(wt, "cookingStage"),
        # armor fields
        "gearSlot": infobox_field(wt, "gearSlot"),
        "gearArmor": infobox_field(wt, "gearArmor"),
        "gearHeatResist": infobox_field(wt, "gearHeatResist"),
        "gearRadResist": infobox_field(wt, "gearRadResist"),
        "setBonusHalf": infobox_field(wt, "gearSetBonusHalf"),
        "setBonusFull": infobox_field(wt, "gearSetBonusFull"),
    }
    it["summary"] = best_summary(wt)
    return it


def main() -> None:
    routed: dict[str, list] = {k: [] for k in CATEGORIES}
    for cat in CATEGORIES:
        members = [
            m["title"] for m in category_members(f"Category:{cat}")
            if m["ns"] == 0 and not LANG_SUFFIX.search(m["title"])
        ]
        print(f"{cat}: {len(members)} pages")
        for i, title in enumerate(members):
            wt = get_wikitext(title)
            time.sleep(0.25)
            it = parse_item(title, wt) if wt else None
            if not it:
                print(f"[{i+1}/{len(members)}] SKIP {title}")
                continue
            routed[cat].append(it)
            if (i + 1) % 50 == 0:
                print(f"  [{i+1}/{len(members)}] done")
    for cat, out in CATEGORIES.items():
        rows = sorted(routed[cat], key=lambda x: x["name"])
        with open(out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print(f"wrote {out}: {len(rows)}")


if __name__ == "__main__":
    main()
