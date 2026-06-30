#!/usr/bin/env python3
"""
SheetReady Pulse — daily refresh.

Picks the next unposted tip from tips.json, prepends a dated <article> to the
feed in index.html AND a matching BlogPosting to the JSON-LD blog, trims both
to the newest ~10 (1:1 article<->BlogPosting invariant), validates, and writes.

JSON-LD is handled by PARSING the real JSON and editing the blogPost array —
never by regex-counting braces (which mis-counts the BreadcrumbList).

Stdlib only. Exits nonzero WITHOUT writing if validation fails, so a bad run
never deploys.
"""

import datetime
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE / "index.html"
TIPS = HERE / "tips.json"
SITEMAP = HERE.parent / "sitemap.xml"  # site root /sitemap.xml
PULSE_LOC = "https://sheetready.vercel.app/pulse/"

MAX_VISIBLE = 10
FEED_START = "<!-- PULSE:FEED-START -->"
FEED_END = "<!-- PULSE:FEED-END -->"


def die(msg):
    print(f"pulse: ERROR - {msg}", file=sys.stderr)
    sys.exit(1)


def fmt_long(d):
    return f"{d.day} {d.strftime('%B')} {d.year}"


def build_article(headline_html, paragraphs_html, date_long):
    body = "\n".join(f"          <p>{p}</p>" for p in paragraphs_html)
    return (
        "\n      <article class=\"entry\">\n"
        f"        <p class=\"date\">{date_long}</p>\n"
        f"        <h2>{headline_html}</h2>\n"
        "        <div class=\"body\">\n"
        f"{body}\n"
        "        </div>\n"
        "      </article>"
    )


def main():
    if not INDEX.exists():
        die(f"{INDEX} not found")
    if not TIPS.exists():
        die(f"{TIPS} not found")

    tips = json.loads(TIPS.read_text(encoding="utf-8"))
    # Post the NEWEST unposted tip. generate_tip.py appends today's AI tip to the
    # end, so this posts that fresh one; if generation failed, it falls back to
    # the most recent pre-written tip in the bank. Either way the deploy happens.
    nxt = next((t for t in reversed(tips) if t.get("posted") is None), None)
    if nxt is None:
        print("pulse: no unposted tips remain - nothing to do.")
        sys.exit(0)

    today = datetime.date.today()
    date_iso = today.isoformat()
    date_long = fmt_long(today)
    headline_text = nxt["headline"]
    description = nxt["description"]
    paragraphs_html = nxt["paragraphs"]  # may contain intentional inline <a> links

    src = INDEX.read_text(encoding="utf-8")

    # ---- 1) Feed (HTML) ----
    s = src.find(FEED_START)
    e = src.find(FEED_END)
    if s == -1 or e == -1 or e < s:
        die("feed markers not found")
    s_end = s + len(FEED_START)
    f_before, f_inner, f_after = src[:s_end], src[s_end:e], src[e:]

    new_article = build_article(html.escape(headline_text, quote=False), paragraphs_html, date_long)
    articles = re.findall(r"\s*<article class=\"entry\">.*?</article>", new_article + f_inner, flags=re.DOTALL)
    if not articles:
        die("no <article> blocks found after insertion")
    kept = articles[:MAX_VISIBLE]
    f_inner_new = "".join(kept) + "\n      "
    article_count = len(kept)
    src = f_before + f_inner_new + f_after

    # ---- 2) JSON-LD (parse real JSON, edit blogPost array) ----
    m = re.search(r'(<script type="application/ld\+json">)(.*?)(</script>)', src, flags=re.DOTALL)
    if not m:
        die("ld+json <script> block not found")
    inner = re.sub(r"<!--.*?-->", "", m.group(2), flags=re.DOTALL)  # drop any comment markers
    try:
        data = json.loads(inner)
    except json.JSONDecodeError as exc:
        die(f"existing JSON-LD does not parse: {exc}")

    graph = data.get("@graph", [])
    blog = next((n for n in graph if n.get("@type") == "Blog"), None)
    if blog is None:
        die("JSON-LD @graph has no Blog node")
    posts = blog.get("blogPost", [])
    posts.insert(0, {"@type": "BlogPosting", "headline": headline_text,
                     "datePublished": date_iso, "dateModified": date_iso,
                     "description": description})
    blog["blogPost"] = posts[:MAX_VISIBLE]
    blog["dateModified"] = date_iso  # the feed itself was freshened today
    post_count = len(blog["blogPost"])

    new_ld = "\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    src = src[:m.start()] + m.group(1) + new_ld + m.group(3) + src[m.end():]

    # ---- 3) Validate (no write on failure) ----
    if article_count != post_count:
        die(f"invariant broken: {article_count} articles vs {post_count} BlogPosting")
    if src.count("<h1") != 1:
        die(f"expected one <h1>, found {src.count('<h1')}")
    m2 = re.search(r'<script type="application/ld\+json">(.*?)</script>', src, flags=re.DOTALL)
    try:
        chk = json.loads(m2.group(1))
    except json.JSONDecodeError as exc:
        die(f"rebuilt JSON-LD does not parse: {exc}")
    b2 = next((n for n in chk.get("@graph", []) if n.get("@type") == "Blog"), None)
    if not b2 or len(b2.get("blogPost", [])) != article_count:
        die("post-write JSON-LD blogPost count != article count")

    # ---- 4) Bump the sitemap's <lastmod> for /pulse/ so Google sees the change
    #         and recrawls (the freshness signal). Non-fatal if the file/entry
    #         can't be found — the content change is what matters most.
    try:
        sm = SITEMAP.read_text(encoding="utf-8")
        pat = re.compile(
            r"(<loc>\s*" + re.escape(PULSE_LOC) + r"\s*</loc>\s*<lastmod>)([^<]*)(</lastmod>)")
        sm2, n = pat.subn(lambda m: m.group(1) + date_iso + m.group(3), sm)
        if n:
            SITEMAP.write_text(sm2, encoding="utf-8")
            print(f"pulse: sitemap lastmod for /pulse/ set to {date_iso}.")
        else:
            print("pulse: WARNING - /pulse/ entry not found in sitemap; skipped lastmod.")
    except FileNotFoundError:
        print("pulse: WARNING - sitemap.xml not found; skipped lastmod.")

    # ---- 5) Write ----
    nxt["posted"] = date_iso
    INDEX.write_text(src, encoding="utf-8")
    TIPS.write_text(json.dumps(tips, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"pulse: added \"{headline_text}\" dated {date_long} (id={nxt['id']}); "
          f"visible entries now {article_count}.")


if __name__ == "__main__":
    main()
