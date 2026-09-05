#!/usr/bin/env python3
"""Scrape Abiotic Factor enemies ({{enemy ...}} infobox).
Output: src/data/enemies.json
"""
import json
import time

from shared import (
    OUT_DIR, get_wikitext, category_members, infobox_field, listed_fields,
    best_summary, clean_html, LANG_SUFFIX,
)


def parse_enemy(title: str, wt: str) -> dict | None:
    if not wt or "{{enemy" not in wt.lower():
        return None
    e = {
        "name": title,
        "slug": title.replace(" ", "_").lstrip("."),
        "type": infobox_field(wt, "type"),
        "codename": infobox_field(wt, "codename"),
        "origin": infobox_field(wt, "origin"),
        "healthHead": infobox_field(wt, "healthHead"),
        "healthTorso": infobox_field(wt, "healthTorso"),
        "meleeDamage": infobox_field(wt, "attackMeleeDamage"),
        "meleeType": infobox_field(wt, "attackMeleeType"),
        "specialName": infobox_field(wt, "attackSpecialName"),
        "specialDamage": infobox_field(wt, "attackSpecialDamage"),
        "specialType": infobox_field(wt, "attackSpecialType"),
        "weakness": infobox_field(wt, "weakness"),
        "resistance": infobox_field(wt, "resistance"),
        "drops": ", ".join(clean_html(v) for v in listed_fields(wt, "drop")),
        "harvest": ", ".join(clean_html(v) for v in listed_fields(wt, "harvest")),
    }
    e["summary"] = best_summary(wt)
    return e


def main() -> None:
    members = [
        m["title"] for m in category_members("Category:Enemies")
        if m["ns"] == 0 and not LANG_SUFFIX.search(m["title"]) and m["title"] != "Enemies"
    ]
    print(f"{len(members)} enemy pages")
    enemies = []
    for i, title in enumerate(members):
        wt = get_wikitext(title)
        time.sleep(0.25)
        e = parse_enemy(title, wt) if wt else None
        if not e:
            print(f"[{i+1}/{len(members)}] SKIP {title}")
            continue
        enemies.append(e)
        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{len(members)}] done")
    with open(OUT_DIR / "enemies.json", "w", encoding="utf-8") as f:
        json.dump(enemies, f, ensure_ascii=False, indent=1)
    print(f"wrote enemies.json: {len(enemies)}")


if __name__ == "__main__":
    main()
