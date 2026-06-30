# -*- coding: utf-8 -*-
"""
SheetReady — landing-page generator.

Reads the shared shell (no-flash theme script + full <style> block) verbatim
from the homepage index.html, then writes:
  templates/<name>/index.html   for each of the 12 products
  templates/index.html          a hub page listing all 12

Re-runnable / idempotent: rewrites the same files each run.

Run:  python _generator/build_pages.py     (from the repo root)

Decisions (documented):
  * MailerLite is OMITTED on every sub-page (consistent across all 12 + hub).
    -> MailerLite preconnect/dns-prefetch hints and the ML lazy-loader are dropped.
    -> Gumroad preconnect/dns-prefetch hints and the Gumroad lazy-loader are KEPT.
  * Homepage-only JS (template filter/search, scroll-spy, dashboard anim,
    mobile sticky bar) is NOT reused. Sub-pages ship a slim script with only the
    dynamic-year, mobile-nav, theme-toggle, and a guarded scroll-reveal.
  * The full shared <style> block is copied verbatim so BOTH the
    @media(prefers-color-scheme:dark) block AND the :root[data-theme="dark"]
    block are present (dark mode works identically).
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INDEX = os.path.join(ROOT, "index.html")
SITE = "https://sheetready.vercel.app"
GUMROAD = "https://supunsandeep.gumroad.com/l/"
OG_IMAGE = "https://sheetready.vercel.app/webpins/og-cover.png"

sys.path.insert(0, HERE)
from products import PRODUCTS, SHORT_TITLES  # noqa: E402


# ----------------------------------------------------------------------------
# Extract the verbatim shared pieces from index.html
# ----------------------------------------------------------------------------
def extract_shared():
    with open(INDEX, "r", encoding="utf-8") as f:
        html = f.read()

    # 1) No-flash theme bootstrap script (the small inline <script> in <head>).
    m = re.search(
        r"<script>\s*\n\s*\(function\(\)\{try\{var t=localStorage\.getItem\('sr-theme'\);.*?\}\)\(\);\s*\n\s*</script>",
        html, re.S)
    if not m:
        raise SystemExit("FATAL: could not find the no-flash theme bootstrap script.")
    no_flash = m.group(0)

    # 2) The entire <style>...</style> block (light tokens + both dark blocks).
    m = re.search(r"<style>.*?</style>", html, re.S)
    if not m:
        raise SystemExit("FATAL: could not find the shared <style> block.")
    style_block = m.group(0)
    # sanity: all three theme layers must be present
    for needle in ('@media (prefers-color-scheme:dark)',
                   ':root[data-theme="dark"]',
                   ':root{'):
        if needle not in style_block:
            raise SystemExit(f"FATAL: shared <style> missing required layer: {needle}")

    # 3) The favicon <link rel="icon" ...> (single line).
    m = re.search(r'<link rel="icon"[^>]*/>', html)
    if not m:
        raise SystemExit("FATAL: could not find the favicon link.")
    favicon = m.group(0)

    # 4) The footer block (used verbatim, minus the homepage anchor hrefs which
    #    we rewrite to absolute / paths so they work from /templates/<name>/).
    m = re.search(r"<footer>.*?</footer>", html, re.S)
    if not m:
        raise SystemExit("FATAL: could not find the footer.")
    footer = m.group(0)

    return no_flash, style_block, favicon, footer


# ----------------------------------------------------------------------------
# Header markup (brand + nav + theme toggle). Hrefs point to the homepage with
# absolute / so they resolve correctly from a /templates/<name>/ page.
# ----------------------------------------------------------------------------
HEADER = '''<header class="topbar">
  <div class="wrap">
    <a class="brand" href="/" aria-label="SheetReady home">
      <svg class="mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
        <rect width="32" height="32" rx="8" fill="#102544"/>
        <rect x="16.5" y="16.5" width="8.5" height="8.5" rx="1.5" fill="#F2B705"/>
        <path d="M18.3 20.9l1.7 1.7 3-3.4" fill="none" stroke="#102544" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        <g stroke="#F2B705" stroke-width="1.7" stroke-linecap="round"><line x1="7" y1="16" x2="25" y2="16"/><line x1="16" y1="7" x2="16" y2="25"/></g>
        <rect x="7" y="7" width="18" height="18" rx="2.5" fill="none" stroke="#F2B705" stroke-width="1.7"/>
        <circle cx="25" cy="25" r="2.4" fill="#F2B705" stroke="#102544" stroke-width="1.2"/>
      </svg>
      <span>Sheet<span class="g">Ready</span></span>
    </a>
    <button class="navtoggle" aria-label="Open menu" aria-expanded="false" aria-controls="primary-nav" id="navBtn">
      <svg id="navIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/></svg>
    </button>
    <div class="nav-backdrop" id="navBackdrop" hidden></div>
    <nav class="nav" id="primary-nav" aria-label="Primary">
      <a href="/templates/">Templates</a>
      <a href="/#how">How it works</a>
      <a href="/#about">About</a>
      <a href="/blog/">Blog</a>
      <a href="/pulse/">Pulse</a>
      <a href="/#faq">FAQ</a>
      <button type="button" class="themetoggle" id="themeToggle" aria-label="Switch to dark theme">
        <svg class="ic-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        <svg class="ic-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M4.2 4.2l1.8 1.8M18 18l1.8 1.8M2 12h2.5M19.5 12H22M4.2 19.8l1.8-1.8M18 6l1.8-1.8"/></svg>
      </button>
      <a class="cta" href="/templates/free-money-tracker/">Get free tracker</a>
    </nav>
  </div>
</header>'''


# Slim sub-page JS: dynamic year + mobile nav + theme toggle + guarded reveal.
# No filter/search/scroll-spy/dashboard/mobile-bar -> no errors on missing nodes.
SUBPAGE_JS = r'''<script>
  (function(){
    var reduce=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    /* ---- dynamic year ---- */
    var y=document.getElementById('yr'); if(y){y.textContent=new Date().getFullYear();}

    /* ---- mobile nav: slide/fade + focus-trap + Esc ---- */
    var btn=document.getElementById('navBtn'),nav=document.getElementById('primary-nav'),
        backdrop=document.getElementById('navBackdrop'),navIcon=document.getElementById('navIcon');
    var menuHTML='<line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/>';
    var xHTML='<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>';
    var navOpen=false;
    function focusables(){return nav.querySelectorAll('a[href],button');}
    function openNav(){
      navOpen=true;nav.classList.add('open');backdrop.hidden=false;
      requestAnimationFrame(function(){nav.classList.add('in');backdrop.classList.add('in');});
      btn.setAttribute('aria-expanded','true');btn.setAttribute('aria-label','Close menu');
      navIcon.innerHTML=xHTML;
      var f=focusables(); if(f.length){f[0].focus();}
    }
    function closeNav(returnFocus){
      navOpen=false;nav.classList.remove('in');backdrop.classList.remove('in');
      btn.setAttribute('aria-expanded','false');btn.setAttribute('aria-label','Open menu');
      navIcon.innerHTML=menuHTML;
      var done=function(){nav.classList.remove('open');backdrop.hidden=true;};
      if(reduce){done();}else{setTimeout(done,220);}
      if(returnFocus){btn.focus();}
    }
    if(btn&&nav){
      btn.addEventListener('click',function(){navOpen?closeNav(true):openNav();});
      backdrop.addEventListener('click',function(){closeNav(false);});
      nav.addEventListener('click',function(e){if(e.target.closest('a')){closeNav(false);}});
      document.addEventListener('keydown',function(e){
        if(!navOpen)return;
        if(e.key==='Escape'){closeNav(true);}
        else if(e.key==='Tab'){
          var f=focusables();if(!f.length)return;
          var first=f[0],last=f[f.length-1];
          if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
          else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
        }
      });
      window.addEventListener('resize',function(){if(window.innerWidth>760&&navOpen){closeNav(false);}});
    }

    /* ---- manual theme toggle (light/dark, overrides the OS) ---- */
    var themeBtn=document.getElementById('themeToggle');
    if(themeBtn){
      var mqDark=window.matchMedia?window.matchMedia('(prefers-color-scheme:dark)'):null;
      function effectiveTheme(){
        var a=document.documentElement.getAttribute('data-theme');
        if(a==='dark'||a==='light')return a;
        return (mqDark&&mqDark.matches)?'dark':'light';
      }
      function syncThemeUI(){
        var eff=effectiveTheme();
        themeBtn.setAttribute('aria-label',eff==='dark'?'Switch to light theme':'Switch to dark theme');
        var color=eff==='dark'?'#0E1726':'#FBFCFE';
        var metas=document.querySelectorAll('meta[name="theme-color"]');
        metas.forEach(function(m){m.setAttribute('content',color);});
      }
      themeBtn.addEventListener('click',function(){
        var next=effectiveTheme()==='dark'?'light':'dark';
        document.documentElement.dataset.theme=next;
        try{localStorage.setItem('sr-theme',next);}catch(e){}
        syncThemeUI();
      });
      if(mqDark&&mqDark.addEventListener){
        mqDark.addEventListener('change',function(){
          if(!document.documentElement.getAttribute('data-theme')){syncThemeUI();}
        });
      }
      syncThemeUI();
    }

    /* ---- guarded scroll reveal (no-op if no .reveal elements) ---- */
    var items=document.querySelectorAll('.reveal');
    if(items.length){
      if(reduce||!('IntersectionObserver'in window)){
        items.forEach(function(el){el.classList.add('in');});
      }else{
        var io=new IntersectionObserver(function(entries){
          entries.forEach(function(en){if(en.isIntersecting){en.target.classList.add('in');io.unobserve(en.target);}});
        },{rootMargin:'0px 0px -8% 0px',threshold:.08});
        items.forEach(function(el){io.observe(el);});
      }
    }
  })();
</script>'''


# Gumroad lazy loader (KEPT verbatim in intent; MailerLite block dropped).
GUMROAD_JS = r'''<script>
  (function(){
    /* ---------- Gumroad overlay (checkout) ----------
       gumroad.js attaches its overlay handler to .gumroad-button links at load.
       Load it on the first hover/touch/focus of ANY buy link; idle fallback
       after window load. Links are real /l/ URLs, so a click works even before
       JS loads (graceful fallback: opens the Gumroad product page). */
    var grLoaded=false;
    function loadGumroad(){
      if(grLoaded)return; grLoaded=true;
      var s=document.createElement('script');
      s.src='https://gumroad.com/js/gumroad.js'; s.async=true;
      document.body.appendChild(s);
    }
    var grBtns=document.querySelectorAll('.gumroad-button');
    var grTriggers=['pointerover','touchstart','focus'];
    function grWarm(){loadGumroad();}
    grBtns.forEach(function(b){
      grTriggers.forEach(function(ev){
        b.addEventListener(ev,grWarm,{once:true,passive:true});
      });
    });
    window.addEventListener('load',function(){
      if('requestIdleCallback'in window){requestIdleCallback(loadGumroad,{timeout:4000});}
      else{setTimeout(loadGumroad,3000);}
    });
  })();
</script>'''


# Tiny page-scoped CSS added AFTER the shared <style> block. Uses existing CSS
# variables so it themes correctly in light + dark. Scoped class names only.
PAGE_CSS = '''<style>
  /* landing-page-specific helpers (scoped; reuse shared CSS variables) */
  .crumbs{font-size:14px;color:var(--muted);padding:22px 0 0;display:flex;flex-wrap:wrap;
    align-items:center;gap:6px}
  .crumbs a{color:var(--navy);text-decoration:none}
  .crumbs a:hover{color:var(--gold-text);text-decoration:underline}
  .crumbs span[aria-current]{color:var(--navy-ink);font-weight:600}
  .crumbs .sep{color:var(--muted);opacity:.6}
  .lp{padding:24px 0 var(--s9)}
  .lp .head{max-width:760px;margin-bottom:18px}
  .lp .cat-kicker{margin-bottom:14px}
  .lp h1{font-size:var(--fs-display);color:var(--navy-ink);letter-spacing:-.022em;line-height:1.08}
  .lp .lead{margin-top:18px;font-size:var(--fs-lead);color:var(--muted);max-width:60ch}
  .lp .priceline{display:flex;flex-wrap:wrap;align-items:center;gap:16px;margin-top:26px}
  .lp .priceline .price{font-family:var(--mono);font-weight:700;font-size:24px;color:var(--navy-ink)}
  .lp .priceline .price.free{color:var(--emerald)}
  .lp .priceline .note{font-size:14px;color:var(--muted)}
  .lp section.block{max-width:760px;margin-top:var(--s7)}
  .lp section.block h2{font-size:var(--fs-h2);color:var(--navy-ink);margin-bottom:14px}
  .lp section.block p{color:var(--ink);font-size:16.5px;line-height:1.7}
  .lp .included{list-style:none;margin:18px 0 0;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .lp .included li{display:flex;align-items:flex-start;gap:11px;background:var(--card);border:1px solid var(--line);
    border-radius:var(--r-md);padding:14px 15px;box-shadow:var(--sh-1),var(--glass-edge);font-size:14.5px;color:var(--ink)}
  .lp .included li .ic{color:var(--emerald);width:20px;height:20px;flex:0 0 auto;margin-top:1px;stroke-width:2.2}
  .lp .buywrap{margin-top:30px;display:flex;flex-wrap:wrap;align-items:center;gap:14px}
  .lp .related{max-width:760px;margin-top:var(--s7);background:var(--surface);border:1px solid var(--line);
    border-radius:var(--r-lg);padding:24px 26px}
  .lp .related h2{font-size:var(--fs-h3);color:var(--navy-ink);margin-bottom:8px}
  .lp .related p{color:var(--muted);font-size:15px;margin-bottom:14px}
  .lp .related ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:10px 14px}
  .lp .related a{display:inline-flex;align-items:center;gap:7px;font-weight:600;font-size:14.5px;
    color:var(--navy);text-decoration:none;background:var(--card);border:1px solid var(--line);
    border-radius:999px;padding:9px 16px;min-height:40px}
  .lp .related a:hover{border-color:var(--gold);color:var(--gold-text)}
  .lp .home-link{margin-top:32px;font-size:15px}
  .lp .home-link a{color:var(--navy);font-weight:600}
  .lp .faq-wrap{max-width:760px;margin-top:var(--s7)}
  .lp .faq-wrap h2{font-size:var(--fs-h2);color:var(--navy-ink);margin-bottom:20px}
  /* hub grid */
  .hub{padding:24px 0 var(--s9)}
  .hub .head{max-width:720px;margin-bottom:8px}
  .hub h1{font-size:var(--fs-display);color:var(--navy-ink)}
  .hub .lead{margin-top:18px;font-size:var(--fs-lead);color:var(--muted);max-width:60ch}
  .hub .tgrid{margin-top:var(--s7);display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
  .hub .tcard{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line);
    border-radius:var(--r-lg);padding:22px 22px 20px;box-shadow:var(--sh-1),var(--glass-edge);
    text-decoration:none;transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease}
  .hub .tcard:hover{transform:translateY(-4px);box-shadow:var(--sh-2),var(--glass-edge);border-color:#d3def1}
  .hub .tcard .cat{font-family:var(--mono);font-size:10.5px;color:var(--navy);letter-spacing:.1em;
    text-transform:uppercase;font-weight:600}
  .hub .tcard h2{font-size:var(--fs-h3);color:var(--navy-ink);margin-top:8px;line-height:1.25}
  .hub .tcard .d{margin-top:9px;font-size:14px;color:var(--muted);flex:1}
  .hub .tcard .p{margin-top:16px;font-family:var(--mono);font-weight:700;font-size:18px;color:var(--navy-ink)}
  .hub .tcard .p.free{color:var(--emerald)}
  @media (max-width:960px){.hub .tgrid{grid-template-columns:repeat(2,1fr)}.lp .included{grid-template-columns:1fr}}
  @media (max-width:560px){.hub .tgrid{grid-template-columns:1fr}.lp .buywrap a.gumroad-button.buy{width:100%;justify-content:center}}
</style>'''


CHECK_SVG = ('<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
             '<polyline points="20 6 9 17 4 12"/></svg>')


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def price_display(price):
    return "Free" if price == "0" else f"${price}"


def build_product_page(p, no_flash, style_block, favicon, footer):
    name = p["name"]
    canonical = f"{SITE}/templates/{name}/"
    gum = f"{GUMROAD}{p['slug']}"
    is_free = p["price"] == "0"

    # ---- JSON-LD @graph (Product + BreadcrumbList) ----
    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Product",
                "name": p["h1"],
                "description": p["ld_desc"],
                "brand": {"@type": "Brand", "name": "SheetReady"},
                "offers": {
                    "@type": "Offer",
                    "price": p["price"],
                    "priceCurrency": "USD",
                    "availability": "https://schema.org/InStock",
                    "url": gum,
                },
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
                    {"@type": "ListItem", "position": 2, "name": "Templates", "item": f"{SITE}/templates/"},
                    {"@type": "ListItem", "position": 3, "name": SHORT_TITLES[name], "item": canonical},
                ],
            },
        ],
    }
    # Validate it parses as JSON (fail loudly if not).
    ld_str = json.dumps(ld, ensure_ascii=False, indent=2)
    json.loads(ld_str)  # raises on malformed
    # confirm offer.url matches the slug
    assert ld["@graph"][0]["offers"]["url"] == gum, f"offer.url mismatch for {name}"

    # ---- sections ----
    sections_html = ""
    for s in p["sections"]:
        sections_html += (
            f'\n      <section class="block">\n'
            f'        <h2>{esc(s["h2"])}</h2>\n'
            f'        <p>{esc(s["body"])}</p>\n'
            f'      </section>'
        )

    # ---- includes ----
    inc_items = "".join(
        f'\n          <li>{CHECK_SVG}<span>{esc(i)}</span></li>'
        for i in p["includes"]
    )

    # ---- FAQ ----
    faq_items = ""
    for qa in p["faq"]:
        faq_items += (
            f'\n        <details>\n'
            f'          <summary>{esc(qa["q"])}<span class="pm" aria-hidden="true">+</span></summary>\n'
            f'          <p class="ans">{esc(qa["a"])}</p>\n'
            f'        </details>'
        )

    # ---- related links ----
    rel_items = "".join(
        f'\n          <li><a href="/templates/{r}/">{esc(SHORT_TITLES[r])} '
        f'<span aria-hidden="true">&rarr;</span></a></li>'
        for r in p["related"]
    )

    # ---- buy button ----
    if is_free:
        buy_cls = "gumroad-button buy free"
        buy_label = "Get it free"
        price_cls = "price free"
        price_txt = "Free"
        note = "$0 — no card required"
    else:
        buy_cls = "gumroad-button buy"
        buy_label = "Get it"
        price_cls = "price"
        price_txt = f"${p['price']}"
        note = "One-time payment · instant download"

    buy_btn = (f'<a class="{buy_cls}" href="{gum}" target="_blank" rel="noopener noreferrer">'
               f'{buy_label} <span class="arr" aria-hidden="true">&rarr;</span></a>')

    # footer hrefs already absolute in source for blog? They use #anchors; rewrite
    # in-page anchors to /#anchor so they work from a sub-page.
    page_footer = footer
    page_footer = page_footer.replace('href="#templates"', 'href="/templates/"')
    page_footer = re.sub(r'href="#([a-zA-Z0-9_-]+)"', r'href="/#\1"', page_footer)

    og_title = p["title"]

    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>

<title>{esc(p["title"])}</title>
<meta name="description" content="{esc(p["meta"])}"/>

<link rel="canonical" href="{canonical}"/>
<meta name="theme-color" content="#FBFCFE" media="(prefers-color-scheme: light)"/>
<meta name="theme-color" content="#0E1726" media="(prefers-color-scheme: dark)"/>
<meta name="robots" content="index,follow"/>

<!-- Warm up Gumroad (buy buttons). No MailerLite on sub-pages. -->
<link rel="preconnect" href="https://gumroad.com"/>
<link rel="dns-prefetch" href="https://gumroad.com"/>
<link rel="preconnect" href="https://assets.gumroad.com"/>
<link rel="dns-prefetch" href="https://assets.gumroad.com"/>

<!-- Open Graph -->
<meta property="og:type" content="website"/>
<meta property="og:site_name" content="SheetReady"/>
<meta property="og:title" content="{esc(og_title)}"/>
<meta property="og:description" content="{esc(p["meta"])}"/>
<meta property="og:url" content="{canonical}"/>
<meta property="og:image" content="{OG_IMAGE}"/>
<meta property="og:image:width" content="1200"/>
<meta property="og:image:height" content="630"/>
<meta property="og:image:alt" content="SheetReady — simple Excel &amp; Google Sheets finance templates"/>

<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{esc(og_title)}"/>
<meta name="twitter:description" content="{esc(p["meta"])}"/>
<meta name="twitter:image" content="{OG_IMAGE}"/>

{favicon}

<!-- JSON-LD: Product + BreadcrumbList -->
<script type="application/ld+json">
{ld_str}
</script>

{no_flash}

{style_block}
{PAGE_CSS}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>

{HEADER}

<div class="wrap">
  <nav class="crumbs" aria-label="Breadcrumb">
    <a href="/">Home</a>
    <span class="sep" aria-hidden="true">&rsaquo;</span>
    <a href="/templates/">Templates</a>
    <span class="sep" aria-hidden="true">&rsaquo;</span>
    <span aria-current="page">{esc(SHORT_TITLES[name])}</span>
  </nav>
</div>

<main id="main">
  <article class="wrap lp">
    <div class="head">
      <span class="kicker cat-kicker">{esc(p["cat"])} template</span>
      <h1>{esc(p["h1"])}</h1>
      <p class="lead">{esc(p["intro"])}</p>
      <div class="priceline">
        <span class="{price_cls}">{price_txt}</span>
        <span class="note">{esc(note)}</span>
      </div>
      <div class="buywrap">
        {buy_btn}
        <a class="btn btn-ghost" href="/templates/">Browse all templates</a>
      </div>
    </div>
{sections_html}

    <section class="block" aria-labelledby="incl-h">
      <h2 id="incl-h">What's Included</h2>
      <ul class="included">{inc_items}
      </ul>
      <div class="buywrap">
        {buy_btn}
      </div>
    </section>

    <section class="faq-wrap" aria-labelledby="faq-h">
      <h2 id="faq-h">Frequently Asked Questions</h2>
      <div class="faq">{faq_items}
      </div>
    </section>

    <aside class="related" aria-labelledby="rel-h">
      <h2 id="rel-h">Related templates</h2>
      <p>{esc(p["related_intro"])}</p>
      <ul>{rel_items}
      </ul>
    </aside>

    <p class="home-link"><a href="/">&larr; Back to the SheetReady home page</a></p>
  </article>
</main>

{page_footer}

{SUBPAGE_JS}

{GUMROAD_JS}
</body>
</html>
'''
    out_dir = os.path.join(ROOT, "templates", name)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path, gum, ld_str


def build_hub(no_flash, style_block, favicon, footer):
    canonical = f"{SITE}/templates/"
    ld = {
        "@context": "https://schema.org",
        "@graph": [{
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
                {"@type": "ListItem", "position": 2, "name": "Templates", "item": canonical},
            ],
        }],
    }
    ld_str = json.dumps(ld, ensure_ascii=False, indent=2)
    json.loads(ld_str)

    cards = ""
    for p in PRODUCTS:
        is_free = p["price"] == "0"
        pcls = "p free" if is_free else "p"
        ptxt = "Free" if is_free else f"${p['price']}"
        cards += (
            f'\n      <a class="tcard" href="/templates/{p["name"]}/">\n'
            f'        <span class="cat">{esc(p["cat"])}</span>\n'
            f'        <h2>{esc(SHORT_TITLES[p["name"]])}</h2>\n'
            f'        <span class="d">{esc(p["ld_desc"])}</span>\n'
            f'        <span class="{pcls}">{ptxt}</span>\n'
            f'      </a>'
        )

    page_footer = footer
    page_footer = page_footer.replace('href="#templates"', 'href="/templates/"')
    page_footer = re.sub(r'href="#([a-zA-Z0-9_-]+)"', r'href="/#\1"', page_footer)

    title = "All Spreadsheet Templates — SheetReady"
    meta = ("Browse all 12 SheetReady spreadsheet templates for budgeting, debt payoff, "
            "savings, cash flow, invoicing, freelancer tax, inventory, and sales — Excel and Google Sheets.")

    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>

<title>{esc(title)}</title>
<meta name="description" content="{esc(meta)}"/>

<link rel="canonical" href="{canonical}"/>
<meta name="theme-color" content="#FBFCFE" media="(prefers-color-scheme: light)"/>
<meta name="theme-color" content="#0E1726" media="(prefers-color-scheme: dark)"/>
<meta name="robots" content="index,follow"/>

<link rel="preconnect" href="https://gumroad.com"/>
<link rel="dns-prefetch" href="https://gumroad.com"/>

<meta property="og:type" content="website"/>
<meta property="og:site_name" content="SheetReady"/>
<meta property="og:title" content="{esc(title)}"/>
<meta property="og:description" content="{esc(meta)}"/>
<meta property="og:url" content="{canonical}"/>
<meta property="og:image" content="{OG_IMAGE}"/>
<meta property="og:image:width" content="1200"/>
<meta property="og:image:height" content="630"/>
<meta property="og:image:alt" content="SheetReady — simple Excel &amp; Google Sheets finance templates"/>

<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{esc(title)}"/>
<meta name="twitter:description" content="{esc(meta)}"/>
<meta name="twitter:image" content="{OG_IMAGE}"/>

{favicon}

<script type="application/ld+json">
{ld_str}
</script>

{no_flash}

{style_block}
{PAGE_CSS}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>

{HEADER}

<div class="wrap">
  <nav class="crumbs" aria-label="Breadcrumb">
    <a href="/">Home</a>
    <span class="sep" aria-hidden="true">&rsaquo;</span>
    <span aria-current="page">Templates</span>
  </nav>
</div>

<main id="main">
  <section class="wrap hub">
    <div class="head">
      <span class="kicker">All templates</span>
      <h1>Spreadsheet Templates for Money and Business</h1>
      <p class="lead">Twelve pre-built Excel and Google Sheets templates for personal budgeting, debt and savings, small-business cash flow, invoicing, freelancer tax, inventory, and sales. Start with the free money tracker, upgrade when you need more.</p>
    </div>
    <div class="tgrid">{cards}
    </div>
  </section>
</main>

{page_footer}

{SUBPAGE_JS}

{GUMROAD_JS}
</body>
</html>
'''
    out_path = os.path.join(ROOT, "templates", "index.html")
    os.makedirs(os.path.join(ROOT, "templates"), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def main():
    no_flash, style_block, favicon, footer = extract_shared()
    print("Extracted shared shell from index.html "
          f"(style {len(style_block)} bytes, footer {len(footer)} bytes).")

    results = []
    for p in PRODUCTS:
        path, gum, ld_str = build_product_page(p, no_flash, style_block, favicon, footer)
        results.append((p["name"], p["slug"], p["price"], path, gum))
        print(f"  wrote {path}")

    hub = build_hub(no_flash, style_block, favicon, footer)
    print(f"  wrote {hub}")

    print(f"\nDone. {len(results)} product pages + 1 hub.")
    return results


if __name__ == "__main__":
    main()
