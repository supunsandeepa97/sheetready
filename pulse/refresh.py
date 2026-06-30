#!/usr/bin/env python3
"""
SheetReady Pulse — daily refresh.

Picks the next unposted tip from tips.json, prepends a dated <article> to the
feed in index.html and a matching BlogPosting to the JSON-LD, trims the visible
list to the newest ~10 (keeping the 1:1 article<->BlogPosting invariant),
validates, and writes both files back.

Stdlib only. Run from anywhere; paths are resolved relative to this file.
Exits nonzero WITHOUT writing if validation fails, so a bad run never deploys.
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

MAX_VISIBLE = 10

FEED_START = "<!-- PULSE:FEED-START -->"
FEED_END = "<!-- PULSE:FEED-END -->"
JSONLD_START = "<!-- PULSE:JSONLD-START -->"
JSONLD_END = "<!-- PULSE:JSONLD-END -->"


def die(msg):
    print(f"pulse: ERROR — {msg}", file=sys.stderr)
    sys.exit(1)


def fmt_long(d: datetime.date) -> str:
    """'29 June 2026' — leading zero stripped, cross-platform."""
    return f"{d.day} {d.strftime('%B')} {d.year}"


def slot(text, start_marker, end_marker, source):
    """Return (before, inner, after) split around a marked region."""
    s = source.find(start_marker)
    e = source.find(end_marker)
    if s == -1 or e == -1 or e < s:
        die(f"could not locate markers {start_marker} .. {end_marker} in {text}")
    s_end = s + len(start_marker)
    return source[:s_end], source[s_end:e], source[e:]


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


def build_blogpost(headline_text, date_iso, description):
    obj = {
        "@type": "BlogPosting",
        "headline": headline_text,
        "datePublished": date_iso,
        "description": description,
    }
    # json.dumps gives us correct escaping for the JSON-LD context.
    return "\n        " + json.dumps(obj, ensure_ascii=False)


def count_articles(feed_inner):
    return len(re.findall(r'<article class="entry">', feed_inner))


def parse_blogposts(jsonld_inner):
    """Return list of BlogPosting object strings from the marked region."""
    # Objects are top-level {...} separated by commas + newlines. Match each {...}.
    return re.findall(r"\{.*?\}", jsonld_inner, flags=re.DOTALL)


def main():
    if not INDEX.exists():
        die(f"{INDEX} not found")
    if not TIPS.exists():
        die(f"{TIPS} not found")

    tips = json.loads(TIPS.read_text(encoding="utf-8"))
    nxt = next((t for t in tips if t.get("posted") is None), None)
    if nxt is None:
        print("pulse: no unposted tips remain — nothing to do.")
        sys.exit(0)

    today = datetime.date.today()
    date_iso = today.isoformat()
    date_long = fmt_long(today)

    headline_text = nxt["headline"]
    headline_html = html.escape(headline_text, quote=False)
    description = nxt["description"]
    # tip paragraphs may contain intentional inline <a> links — keep as-is.
    paragraphs_html = nxt["paragraphs"]

    src = INDEX.read_text(encoding="utf-8")

    # ---- 1) Feed region ----
    f_before, f_inner, f_after = slot("feed", FEED_START, FEED_END, src)
    new_article = build_article(headline_html, paragraphs_html, date_long)
    f_inner_new = new_article + f_inner

    # trim to newest MAX_VISIBLE articles
    articles = re.findall(r"\s*<article class=\"entry\">.*?</article>",
                          f_inner_new, flags=re.DOTALL)
    if not articles:
        die("no <article> blocks found after insertion")
    kept_articles = articles[:MAX_VISIBLE]
    f_inner_trimmed = "".join(kept_articles)
    # re-pad so the closing marker stays indented on its own line
    f_inner_trimmed = f_inner_trimmed + "\n      "
    article_count = len(kept_articles)

    # ---- 2) JSON-LD region ----
    j_before, j_inner, j_after = slot("JSON-LD", JSONLD_START, JSONLD_END, src)
    existing_posts = parse_blogposts(j_inner)
    new_post = json.dumps(
        {"@type": "BlogPosting", "headline": headline_text,
         "datePublished": date_iso, "description": description},
        ensure_ascii=False,
    )
    all_posts = [new_post] + existing_posts
    kept_posts = all_posts[:MAX_VISIBLE]
    j_inner_new = "\n        " + ",\n        ".join(kept_posts) + "\n        "
    post_count = len(kept_posts)

    # rebuild the document
    new_src = (f_before + f_inner_trimmed + f_after)
    # the JSON-LD markers live in the original src; re-split the rebuilt doc
    j_before2, _j_inner2, j_after2 = slot("JSON-LD", JSONLD_START, JSONLD_END, new_src)
    new_src = j_before2 + j_inner_new + j_after2

    # ---- 3) Validate (no write on failure) ----
    if article_count != post_count:
        die(f"invariant broken: {article_count} articles vs {post_count} BlogPosting objects")

    if new_src.count("<h1") != 1:
        die(f"expected exactly one <h1>, found {new_src.count('<h1')}")

    # JSON-LD must still parse: pull the whole ld+json block and json.loads it.
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>',
                  new_src, flags=re.DOTALL)
    if not m:
        die("could not find the ld+json <script> block to validate")
    ld_raw = m.group(1)
    # strip the HTML comment markers before parsing (comments are invalid JSON)
    ld_clean = re.sub(r"<!--.*?-->", "", ld_raw, flags=re.DOTALL)
    try:
        data = json.loads(ld_clean)
    except json.JSONDecodeError as exc:
        die(f"JSON-LD no longer parses as JSON: {exc}")

    # confirm the parsed BlogPosting count matches the article count too
    blog = next((n for n in data.get("@graph", []) if n.get("@type") == "Blog"), None)
    if blog is None:
        die("JSON-LD @graph is missing the Blog node")
    parsed_posts = blog.get("blogPost", [])
    if len(parsed_posts) != article_count:
        die(f"parsed BlogPosting count {len(parsed_posts)} != article count {article_count}")

    # ---- 4) Write back ----
    nxt["posted"] = date_iso
    INDEX.write_text(new_src, encoding="utf-8")
    TIPS.write_text(json.dumps(tips, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"pulse: added \"{headline_text}\" dated {date_long} "
          f"(id={nxt['id']}); visible entries now {article_count}.")


if __name__ == "__main__":
    main()
