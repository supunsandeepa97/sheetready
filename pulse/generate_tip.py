#!/usr/bin/env python3
"""
SheetReady Pulse — daily AI tip generator (the "Cairnsite-style" fresh content).

Calls the Anthropic Messages API to WRITE one brand-new, original money/small-
business tip, validates it hard against the tips.json schema, and appends it
(posted=null) so refresh.py can insert it into the page next.

Design rules:
  * The AI only AUTHORS content. It never touches index.html or the JSON-LD —
    refresh.py does the structural edit + the article<->BlogPosting invariant.
  * Resilient: ANY failure (no key, network, bad/duplicate JSON) prints a notice
    and exits 0 WITHOUT writing, so refresh.py simply posts a pre-written
    fallback tip and the daily deploy still happens. A bad API day never breaks.

Stdlib only. Needs env ANTHROPIC_API_KEY (set as a GitHub repo secret).
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TIPS = HERE / "tips.json"

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"   # cheap + fast; a short tip needs no more
MAX_DESC = 155


def notice(msg):
    # Non-fatal: print and exit 0 so the pipeline falls back to a pre-written tip.
    print(f"generate_tip: {msg} - falling back to a pre-written tip.")
    sys.exit(0)


def kebab(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:48] or "tip"


def main():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        notice("no ANTHROPIC_API_KEY in env")

    tips = json.loads(TIPS.read_text(encoding="utf-8"))
    existing_headlines = {t["headline"].strip().lower() for t in tips}
    existing_ids = {t["id"] for t in tips}
    # Show the model recent headlines so it doesn't repeat a theme.
    recent = [t["headline"] for t in tips[-60:]]

    system = (
        "You write short, original tips for SheetReady, a brand selling simple "
        "Excel/Google Sheets templates for personal budgeting, freelancing, and "
        "small-business money management. Voice: clear, warm, practical, plain "
        "English for an international audience. You give genuinely useful, "
        "evergreen money/organisation advice."
    )
    user = (
        "Write ONE brand-new tip as a single JSON object with EXACTLY these keys:\n"
        '  "headline": a specific, benefit-led sentence (no period at the end, '
        "max ~80 chars)\n"
        '  "paragraphs": an array of 2 or 3 short paragraphs (plain prose strings, '
        "40-90 words each)\n"
        '  "description": a meta-description summary, MAX 155 characters\n\n'
        "STRICT RULES:\n"
        "- 100% original. Do NOT reuse any of these existing headlines or their "
        "angle:\n  " + "\n  ".join(f"- {h}" for h in recent) + "\n"
        "- NO prices, NO dollar amounts, NO specific statistics or percentages, "
        "NO fabricated studies or data.\n"
        "- NO URLs, NO links, NO HTML tags, NO markdown. Plain sentences only.\n"
        "- NO investment, tax, or legal advice; keep it to budgeting/organising/"
        "habits a spreadsheet helps with.\n"
        "- Do not mention competitors. You may mention 'a spreadsheet' or "
        "'a tracker' generically.\n\n"
        "Output ONLY the JSON object, nothing else."
    )

    body = json.dumps({
        "model": MODEL,
        "max_tokens": 700,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode("utf-8")

    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
    except Exception as exc:  # network / auth / rate limit
        notice(f"API call failed: {repr(exc)[:160]}")

    try:
        text = "".join(b.get("text", "") for b in resp.get("content", [])).strip()
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        tip = json.loads(m.group(0) if m else text)
    except Exception as exc:
        notice(f"could not parse model JSON: {repr(exc)[:160]}")

    # ---- hard validation (reject rather than post something malformed) ----
    headline = str(tip.get("headline", "")).strip()
    paras = tip.get("paragraphs", [])
    desc = str(tip.get("description", "")).strip()
    if not headline or len(headline) > 120:
        notice("missing/too-long headline")
    if not isinstance(paras, list) or not (2 <= len(paras) <= 3):
        notice("paragraphs must be a list of 2-3 items")
    if not all(isinstance(p, str) and p.strip() for p in paras):
        notice("empty paragraph")
    if any(re.search(r"https?://|</?\w+>|\$\d|\d+%", p) for p in paras + [headline, desc]):
        notice("contains a banned token (url/html/price/percent)")
    if not desc:
        desc = (paras[0][:MAX_DESC]).rsplit(" ", 1)[0]
    if len(desc) > MAX_DESC:
        desc = desc[:MAX_DESC].rsplit(" ", 1)[0]
    if headline.strip().lower() in existing_headlines:
        notice("duplicate headline")

    tid = kebab(headline)
    base = tid
    n = 2
    while tid in existing_ids:
        tid = f"{base}-{n}"
        n += 1

    tips.append({
        "id": tid,
        "headline": headline,
        "paragraphs": [p.strip() for p in paras],
        "description": desc,
        "posted": None,
    })
    TIPS.write_text(json.dumps(tips, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f'generate_tip: added AI tip "{headline}" (id={tid}); bank now {len(tips)}.')


if __name__ == "__main__":
    main()
