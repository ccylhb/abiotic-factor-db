#!/usr/bin/env python3
"""Shared helpers for Abiotic Factor wiki scrapers."""
import re
import time
from pathlib import Path

import requests

API = "https://abioticfactor.wiki.gg/api.php"
PROXY = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
OUT_DIR = Path(__file__).resolve().parent.parent / "src" / "data"
HEADERS = {"User-Agent": "FactorDB scraper (site build, contact via github)"}

session = requests.Session()
session.proxies.update(PROXY)
session.headers.update(HEADERS)

LANG_SUFFIX = re.compile(r"/[a-z]{2}(-[a-z]+)?$", re.I)


# --- wiki 魔术字展开 ---------------------------------------------------------
# strip_templates() 会整段删掉无名模板，{{PAGENAME}}（条目名）随之消失，
# 正文出现 "The is a ..." 残句。必须在清洗前展开成真实文本。
_MAGIC_TITLE = re.compile(r"\{\{\s*(?:SUB|BASE|FULL)?PAGENAME(?:E)?\s*\}\}", re.I)
_MAGIC_GAME = re.compile(r"\{\{\s*(?:Gamename|Game|SITENAME|Sitename)\s*\}\}", re.I)
_MAGIC_DROP = re.compile(
    r"\{\{\s*(?:DISPLAYTITLE|DEFAULTSORT|#(?:expr|var|if|ifeq|ifexist|switch|tag|invoke|time|pos|len|replace|sub|explode|titleparts)[^}]*)\}\}",
    re.I,
)


def expand_magic(wt: str | None, title: str) -> str | None:
    """把 {{PAGENAME}} 换成条目名，丢弃解析器函数等元魔术字。"""
    if not wt:
        return wt
    wt = _MAGIC_TITLE.sub(lambda _m: title, wt)
    wt = _MAGIC_GAME.sub("Abiotic Factor", wt)
    wt = _MAGIC_DROP.sub("", wt)
    return wt


def get_wikitext(title: str) -> str | None:
    for attempt in range(6):
        try:
            r = session.get(
                API,
                params={"action": "parse", "page": title, "prop": "wikitext", "format": "json"},
                timeout=30,
            )
            if r.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"  429 {title}, backoff {wait}s")
                time.sleep(wait)
                continue
            d = r.json()
            if "parse" in d:
                return expand_magic(d["parse"]["wikitext"]["*"], title)
            if r.status_code != 200:
                print(f"  HTTP {r.status_code} {title}, backoff")
                time.sleep(15 * (attempt + 1))
                continue
            return None
        except Exception as e:
            print(f"  retry {title}: {e}")
            time.sleep(2 * (attempt + 1))
    return None


def category_members(title: str) -> list[dict]:
    """Category members with continuation support."""
    out, cont = [], {}
    for attempt in range(3):
        try:
            while True:
                params = {
                    "action": "query", "list": "categorymembers", "cmtitle": title,
                    "cmlimit": "500", "format": "json", **cont,
                }
                r = session.get(API, params=params, timeout=30)
                d = r.json()
                out += d["query"]["categorymembers"]
                if "continue" in d:
                    cont = d["continue"]
                    time.sleep(0.2)
                else:
                    return out
        except Exception as e:
            print(f"  retry members {title}: {e}")
            time.sleep(2 * (attempt + 1))
    return out


def clean_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_html(val: str) -> str:
    return re.sub(r"<[^>]+>", "", val).strip()


def strip_tables(text: str) -> str:
    """删除 wiki 表格 {|...|}（支持嵌套、单行/多行）与 HTML <table>。

    abiotic 的 wiki 把数值表放在正文之前，且整张表常压成一行；
    strip_templates 不处理表格标记，表格会被当简介输出（线上可见 `{|class=wikitable`）。
    """
    text = re.sub(r"<table\b.*?</table>", "", text, flags=re.S | re.I)
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("{|", i):
            depth, j = 0, i
            while j < n:
                if text.startswith("{|", j):
                    depth += 1
                    j += 2
                elif text.startswith("|}", j):
                    depth -= 1
                    j += 2
                    if depth == 0:
                        break
                else:
                    j += 1
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


_HATNOTE = re.compile(
    r"\{\{\s*(?:Otherlink|Otheruses|Disambig\w*|Disambiguation|For|About|Main|"
    r"See also|Hatnote|Redirect|Distinguish)\b[^{}]*\}\}",
    re.I,
)


def strip_templates(text: str) -> str:
    """Templates WITH positional args -> args joined ({{Col|No}} -> No);
    nameless/named-only templates vanish. {{PAGENAME}} -> ''."""
    text = _HATNOTE.sub("", text)          # 顶注模板整段丢弃，避免拼成假正文
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    while "{{" in text:
        def repl(m: "re.Match[str]") -> str:
            parts = m.group(1).split("|")
            args = [p.strip() for p in parts[1:] if p.strip()]
            return " ".join(args)
        new = re.sub(r"\{\{([^{}]*)\}\}", repl, text)
        if new == text:
            break
        text = new
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    return text.replace("'''", "").replace("''", "")


def infobox_field(wikitext: str, field: str) -> str:
    """Field value from a multiline {{template}} infobox.
    [ \\t]* (not \\s*) after "=" so the match never crosses into the next field."""
    m = re.search(rf"^\|\s*{re.escape(field)}[ \t]*=[ \t]*(.*)", wikitext, flags=re.M)
    if not m:
        return ""
    val = m.group(1).split("\n")[0]
    return clean_ws(strip_templates(val))


def intro_text(wikitext: str, limit: int = 600) -> str:
    """First prose paragraph before any == heading (tables stripped first)."""
    body = re.split(r"\n==+ ", wikitext, maxsplit=1)[0]
    body = strip_tables(body)
    body = strip_templates(body)
    paras = []
    for p in body.split("\n"):
        p = clean_ws(p)
        if len(p) <= 40:
            continue
        if p.count("=") >= 2 and "http" not in p:
            continue
        if p.lstrip().startswith(("|", "!", "{", "}")):
            continue
        paras.append(p)
    return (paras[0] if paras else "")[:limit]


def table_prose(wikitext: str, min_len: int = 80) -> str:
    """在 wiki 表格里取最长的单元格文本 —— 纯数值表会自然落选，
    含长句的表格（如敌人 CONTAINMENT PROTOCOLS 单元格）会被选中。"""
    best = ""
    for m in re.finditer(r"\{\|(.*?)\|\}", wikitext, flags=re.S):
        raw = strip_templates(m.group(1))
        for cell in re.split(r"\|-+|\|\}|!!|\|\|\s*|[|!]", raw):
            c = clean_ws(cell).strip("{}[]-!| ").strip()
            if len(c) >= min_len and len(c) > len(best):
                best = c
    return best


def best_summary(wikitext: str, limit: int = 600) -> str:
    """Intro paragraph first, else first substantive section,
    else longest table cell, else infobox description."""
    skip = {"updates", "gallery", "references", "external links", "see also",
            "trivia", "sources", "source", "upgrading", "crafting", "notes"}
    s = intro_text(wikitext)
    if len(s) >= 40:
        return s[:limit]
    for m in re.finditer(r"==+\s*([^=\n]+?)\s*==+\n(.*?)(?=\n==|\Z)", wikitext, flags=re.S):
        if m.group(1).strip().lower() in skip:
            continue
        txt = clean_ws(strip_templates(strip_tables(m.group(2))))
        if len(txt) >= 80:
            return txt[:limit]
    t = table_prose(wikitext)
    if len(t) >= 80:
        return t[:limit]
    for f in ("description", "flavorText"):
        v = infobox_field(wikitext, f)
        if len(v) >= 20:
            return v[:limit]
    return s


def listed_fields(wikitext: str, prefix: str, max_n: int = 10) -> list[str]:
    """Collect values from drop1..drop10 / harvest1..10 style fields."""
    vals = []
    for i in range(1, max_n + 1):
        v = infobox_field(wikitext, f"{prefix}{i}")
        if v and v.lower() not in ("none", "n/a", "-"):
            vals.append(v)
    return vals
