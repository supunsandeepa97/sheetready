# -*- coding: utf-8 -*-
"""Self-verification for the generated landing pages + homepage wiring."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from products import PRODUCTS, SHORT_TITLES  # noqa

SITE = "https://sheetready.vercel.app"
GUM = "https://supunsandeep.gumroad.com/l/"
ok = True

print("=== 1. FILE EXISTENCE (12 product pages + hub) ===")
for p in PRODUCTS:
    fp = os.path.join(ROOT, "templates", p["name"], "index.html")
    exists = os.path.isfile(fp)
    ok &= exists
    print(f"  [{'OK' if exists else 'MISSING'}] {fp}")
hub = os.path.join(ROOT, "templates", "index.html")
print(f"  [{'OK' if os.path.isfile(hub) else 'MISSING'}] {hub}")
ok &= os.path.isfile(hub)

print("\n=== 2. PER-PAGE JSON-LD PARSE + offer.url == /l/<slug> + dark blocks ===")
print(f"  {'slug':8} {'price':5} {'JSONLD':7} {'offer.url OK':12} {'darkA':6} {'darkB':6}  page")
for p in PRODUCTS:
    fp = os.path.join(ROOT, "templates", p["name"], "index.html")
    html = open(fp, encoding="utf-8").read()
    m = re.search(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', html, re.S)
    parsed = False
    offer_ok = False
    try:
        data = json.loads(m.group(1))
        parsed = True
        prod = next(n for n in data["@graph"] if n["@type"] == "Product")
        bc = next(n for n in data["@graph"] if n["@type"] == "BreadcrumbList")
        offer_ok = (prod["offers"]["url"] == GUM + p["slug"]
                    and prod["offers"]["price"] == p["price"]
                    and len(bc["itemListElement"]) == 3)
    except Exception as e:
        print("    ERROR parsing", p["name"], e)
    darkA = "@media (prefers-color-scheme:dark)" in html
    darkB = ':root[data-theme="dark"]' in html
    canon_ok = f'<link rel="canonical" href="{SITE}/templates/{p["name"]}/"/>' in html
    h1_ok = html.count("<h1>") == 1
    page_ok = parsed and offer_ok and darkA and darkB and canon_ok and h1_ok
    ok &= page_ok
    print(f"  {p['slug']:8} {p['price']:5} {'yes' if parsed else 'NO':7} "
          f"{'yes' if offer_ok else 'NO':12} {'yes' if darkA else 'NO':6} "
          f"{'yes' if darkB else 'NO':6}  {p['name']}  "
          f"{'' if (canon_ok and h1_ok) else '(canon=%s h1count=%d)'%(canon_ok, html.count('<h1>'))}")

print("\n=== 3. HOMEPAGE PRESERVE-LIST GREP ===")
idx = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
gsc = idx.count("google-site-verification")
mlform = idx.count('<div class="ml-embedded" data-form="J3MzPf"></div>')
mlacct = idx.count("ml('account','2476370')")
gum_btn = len(re.findall(r'class="gumroad-button buy', idx)) + len(re.findall(r'class="btn btn-gold gumroad-button"', idx))
gum_total = idx.count("gumroad-button")
h3links = len(re.findall(r'<h3><a href="/templates/', idx))
jsonld = idx.count('"@type": "Organization"')
print(f"  google-site-verification meta : {gsc}  (expect 1)")
print(f"  data-form=\"J3MzPf\" div        : {mlform}  (expect 1)")
print(f"  ml('account','2476370')       : {mlacct}  (expect 1)")
print(f"  total .gumroad-button refs     : {gum_total}")
print(f"  h3 -> /templates/ links        : {h3links}  (expect 12)")
print(f"  Organization JSON-LD node      : {jsonld}  (expect 1)")
# count actual buy links to product slugs
buy_links = len(re.findall(r'gumroad\.com/l/[a-z0-9]+', idx))
print(f"  gumroad.com/l/<slug> links     : {buy_links}")
preserve_ok = (gsc == 1 and mlform == 1 and mlacct == 1 and h3links == 12 and jsonld == 1)
ok &= preserve_ok

print("\n=== 4. HUB PAGE CHECKS ===")
h = open(hub, encoding="utf-8").read()
hub_canon = f'<link rel="canonical" href="{SITE}/templates/"/>' in h
hub_ld = h.count("BreadcrumbList") >= 1
hub_h1 = h.count("<h1>") == 1
hub_links = len(re.findall(r'href="/templates/[a-z0-9-]+/"', h))
print(f"  canonical /templates/ : {hub_canon}")
print(f"  BreadcrumbList present: {hub_ld}")
print(f"  single <h1>           : {hub_h1}")
print(f"  links to product pages: {hub_links}  (expect >=12)")
ok &= hub_canon and hub_ld and hub_h1 and hub_links >= 12

print("\n=== 5. NO google-site-verification ON SUBPAGES ===")
bad = []
for p in PRODUCTS:
    fp = os.path.join(ROOT, "templates", p["name"], "index.html")
    if "google-site-verification" in open(fp, encoding="utf-8").read():
        bad.append(p["name"])
if "google-site-verification" in h:
    bad.append("templates/index.html")
print("  subpages with GSC meta (expect none):", bad or "none")
ok &= not bad

print("\n=== 6. SITEMAP ===")
sm = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8").read()
sm_hub = f"{SITE}/templates/</loc>" in sm
sm_prods = all(f"{SITE}/templates/{p['name']}/</loc>" in sm for p in PRODUCTS)
print(f"  /templates/ in sitemap : {sm_hub}")
print(f"  all 12 product URLs    : {sm_prods}")
ok &= sm_hub and sm_prods

print("\n=== RESULT:", "ALL CHECKS PASSED" if ok else "FAILURES PRESENT", "===")
sys.exit(0 if ok else 1)
