# -*- coding: utf-8 -*-
"""
One-off (idempotent) homepage wiring:
  For each .card <article>, find the Gumroad slug in its buy link, map it to the
  /templates/<name>/ folder, and wrap the card's <h3> INNER TEXT in an <a> to
  that landing page. Leaves the buy buttons, JSON-LD, GSC meta, MailerLite, OG,
  canonical, prices, and counts untouched.

Re-runnable: if an <h3> already contains an <a>, it is skipped.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INDEX = os.path.join(ROOT, "index.html")

sys.path.insert(0, HERE)
from products import PRODUCTS  # noqa: E402

SLUG_TO_NAME = {p["slug"]: p["name"] for p in PRODUCTS}

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

# Split into <article class="card ...">...</article> blocks and transform each.
article_re = re.compile(r'(<article class="card[^"]*"[^>]*>)(.*?)(</article>)', re.S)

wired = 0
skipped = 0
missing = 0


def transform(m):
    global wired, skipped, missing
    open_tag, inner, close_tag = m.group(1), m.group(2), m.group(3)

    # find slug from the buy link inside this card
    sm = re.search(r'gumroad\.com/l/([a-zA-Z0-9]+)', inner)
    if not sm:
        missing += 1
        return m.group(0)
    slug = sm.group(1)
    name = SLUG_TO_NAME.get(slug)
    if not name:
        missing += 1
        return m.group(0)

    # locate the <h3>...</h3> in this card
    h3m = re.search(r'<h3>(.*?)</h3>', inner, re.S)
    if not h3m:
        missing += 1
        return m.group(0)
    h3_inner = h3m.group(1)

    # already wired?
    if '<a ' in h3_inner:
        skipped += 1
        return m.group(0)

    new_h3 = f'<h3><a href="/templates/{name}/">{h3_inner}</a></h3>'
    new_inner = inner[:h3m.start()] + new_h3 + inner[h3m.end():]
    wired += 1
    return open_tag + new_inner + close_tag


html = article_re.sub(transform, html)

with open(INDEX, "w", encoding="utf-8") as f:
    f.write(html)

print(f"wired={wired} skipped(existing)={skipped} missing-slug={missing}")
