#!/usr/bin/env python3
"""一次性修补：把 enemies.json / food.json 里 summary 为「原始 wikitext 表格」的
记录，用修好的 best_summary() 重新计算（name 即页面标题，见 scrape_enemies.parse_enemy）。
用法: python _fix_summaries.py [--apply]
"""
import json
import sys
from pathlib import Path

from shared import OUT_DIR, get_wikitext, best_summary

BAD = ("{|", "|}", "|-", "!!")
TARGETS = ["enemies.json", "food.json"]


def is_bad(s: str) -> bool:
    if not isinstance(s, str) or not s:
        return False
    st = s.lstrip()
    return st.startswith("{|") or "{|" in s or "!!" in s


def main() -> None:
    apply = "--apply" in sys.argv
    total_fixed = 0
    for fn in TARGETS:
        p = OUT_DIR / fn
        rows = json.load(open(p, encoding="utf-8"))
        bad = [r for r in rows if is_bad(r.get("summary"))]
        print(f"\n### {fn}: {len(rows)} 条，待修 {len(bad)}")
        fixed = 0
        for r in bad:
            name = r.get("name") or r.get("title")
            wt = get_wikitext(name)
            if not wt:
                print(f"  !! 取不到 wikitext: {name}")
                continue
            new = best_summary(wt)
            if is_bad(new):
                print(f"  !! 新值仍含表格: {name} => {new[:80]!r}")
                continue
            if new != r["summary"]:
                r["summary"] = new
                fixed += 1
                if fixed <= 3:
                    print(f"  [样例] {name} => {new[:100]!r}")
        print(f"  已重算 {fixed} 条")
        if apply:
            json.dump(rows, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"  已写回 {p}")
        total_fixed += fixed
    print(f"\n合计重算 {total_fixed} 条，apply={apply}")


if __name__ == "__main__":
    main()
