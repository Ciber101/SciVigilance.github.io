#!/usr/bin/env python3
"""Build the SciVigilance Weekly email digest from the site's data files.

Usage: python3 scripts/build_digest.py [--out digest.html] [--json meta.json]
Only real data from data/*.json is used. Kit's "Text only" template adds the
mailing address + unsubscribe footer automatically.
"""
import argparse, html, json, os, re
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://ciber101.github.io/SciVigilance.github.io/"
XURL = "https://x.com/SciVigil"
ACC, TXT, DIM, BG, CARD, LINE = "#f5a623", "#e8ecf4", "#a7b0c2", "#0b0e17", "#141927", "#262d40"
NOW = datetime.now(timezone.utc)

AUTH = {"NASA": 6, "ESA": 6, "Quanta Magazine": 5, "Science News": 5, "New Scientist": 5,
        "MIT News": 5, "Nature": 6, "Science": 6, "Universe Today": 4, "Phys.org": 4,
        "ScienceDaily": 4, "Google DeepMind": 5, "Ars Technica": 4, "MIT Technology Review": 4,
        "The Verge": 3, "ScienceAlert": 3, "The Decoder": 3, "MarkTechPost": 2, "Hugging Face": 3,
        "Simon Willison": 3}
TAGW = {"Space": 3, "Physics": 2, "AI": 1, "Tech": 1, "Earth": 1, "Biology": 1, "Health": 0}
BREAK = re.compile(r"\b(first|discover|breakthrough|record|launch|new|reveals?|finally|mission)\b", re.I)
MODEL = re.compile(r"\b(model|release[sd]?|introduc|launch|open|weights|LLM|Gemini|Claude|GPT|Qwen|Llama|Mistral|GLM|Muse|Kimi|DeepSeek)", re.I)
STOP = {"AI", "The", "A", "An", "New", "How", "Introducing", "Meet", "What", "Why", "Our", "Its",
        "Google", "Meta", "OpenAI", "Anthropic", "Alibaba", "Says", "Model", "Models"}
BAD_X = re.compile(r"(seeks|hiring|job|careers|New Short|#shorts|join our)", re.I)
SCI_X = re.compile(r"(star|planet|galax|quantum|gravity|cell|gene|climate|moon|mars|nasa|esa|telescope|"
                   r"physic|particle|black hole|dwarf|asteroid|lander|rover|ai\b|immun|brain|ocean)", re.I)

def load(name, default):
    try:
        with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def e(s): return html.escape(str(s or ""), quote=True)

def age_days(ts):
    try: return max(0.0, (NOW - datetime.fromisoformat(str(ts).replace("Z", "+00:00"))).total_seconds() / 86400)
    except Exception: return 7.0

def one_line(s, n=130):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    s = m.group(1) if m and len(m.group(1)) >= 40 else s
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"

def score(a):
    s = AUTH.get(a.get("source"), 2) + max(TAGW.get(t, 0) for t in a.get("tags", []) or ["x"]) if a.get("tags") else AUTH.get(a.get("source"), 2)
    if BREAK.search(a.get("title", "")): s += 1
    return s - 0.5 * age_days(a.get("ts") or a.get("date"))

def keys(t): return {w for w in re.findall(r"[A-Z][\w\-\.]*|\w*\d\w*", t) if w not in STOP}

def x_text(t): return re.sub(r"\s+", " ", re.sub(r"https://t\.co/\S+", "", t or "")).strip()

# ---------- HTML pieces ----------
def head(title):
    return (f'<tr><td class="sv-pad" style="padding:30px 24px 6px;"><div style="color:{ACC};font-size:12px;'
            f'letter-spacing:2px;text-transform:uppercase;font-weight:700;border-bottom:1px solid {LINE};'
            f'padding-bottom:8px;">{e(title)}</div></td></tr>')

def row(title, url, summary="", meta="", num=None):
    n = (f'<td width="28" valign="top" style="color:{ACC};font-weight:700;font-size:15px;padding-top:1px;">{num}</td>') if num else ""
    return (f'<tr><td class="sv-pad" style="padding:8px 24px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{n}'
            f'<td valign="top"><a href="{e(url)}" style="color:{TXT};font-weight:600;text-decoration:none;font-size:15px;line-height:1.4;">{e(title)}</a>'
            + (f'<div style="color:{DIM};font-size:13px;line-height:1.5;margin-top:3px;">{e(summary)}</div>' if summary else "")
            + (f'<div style="color:{ACC};font-size:12px;margin-top:3px;">{e(meta)}</div>' if meta else "")
            + '</td></tr></table></td></tr>')

def xrow(name, text, url):
    return (f'<tr><td class="sv-pad" style="padding:8px 24px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            f'<tr><td style="background:{CARD};border-left:3px solid {ACC};padding:12px 14px;border-radius:4px;">'
            f'<div style="color:{ACC};font-size:12px;font-weight:700;">{e(name)}</div>'
            f'<div style="color:{TXT};font-size:14px;line-height:1.5;margin-top:4px;">{e(one_line(text, 220))}</div>'
            f'<a href="{e(url)}" style="color:{ACC};font-size:12px;">View on X &rarr;</a></td></tr></table></td></tr>')

def build():
    latest = load("latest.json", {})
    arts, ai = latest.get("articles", []), latest.get("ai", [])
    shorts = load("shorts.json", {}).get("shorts", [])
    mine = load("x_raw.json", {}).get("data", [])
    accts = {a["handle"]: a for a in load("xfeatured.json", {}).get("accounts", [])}

    # 1. Top stories: ranked, deduped, max 2 from one source
    top, seen, per = [], [], {}
    arts = [a for a in arts if not re.match(r"APOD:", a.get("title", "")) and "APODArchive" not in a.get("summary", "")]
    for a in sorted(arts, key=score, reverse=True):
        k = keys(a["title"])
        if any(len(k & s) >= 2 for s in seen) or per.get(a["source"], 0) >= 2: continue
        top.append(a); seen.append(k); per[a["source"]] = per.get(a["source"], 0) + 1
        if len(top) == 5: break
    used = {a["url"] for a in top}

    # 2. AI: model/frontier items, one per release
    ai_items, aseen = [], []
    for a in sorted(ai, key=lambda a: (bool(MODEL.search(a["title"])), score(a)), reverse=True):
        k = keys(a["title"])
        if any(k & s for s in aseen): continue
        ai_items.append(a); aseen.append(k)
        if len(ai_items) == 3: break

    # 3. Space & launches: top SpaceX post + 2 space articles not in top 5
    spx = (accts.get("SpaceX") or {}).get("posts", [])
    space = [a for a in sorted(arts, key=score, reverse=True) if "Space" in a.get("tags", []) and a["url"] not in used][:2]

    # 4. Voices: Elon + one other agency/rocket company post
    elon = ((accts.get("elonmusk") or {}).get("posts") or [None])[0]
    other = None
    for h in ["NASA", "blueorigin", "esa", "RocketLab", "ulalaunch", "isro", "Arianespace", "FireflySpace", "relativityspace"]:
        ps = [p for p in (accts.get(h) or {}).get("posts", []) if len(x_text(p["text"])) >= 50
              and not (spx and "Space_Station" in p["text"] and "Space_Station" in spx[0]["text"])]
        if ps: other = (accts[h]["name"] if accts[h].get("name") else h, ps[0]); break

    # 5. @SciVigil: this week's science posts, no job ads / Short promos
    best = [p for p in mine if age_days(p.get("created_at")) <= 7 and not BAD_X.search(p.get("text", ""))]
    best.sort(key=lambda p: (bool(SCI_X.search(p["text"])), p.get("created_at", "")), reverse=True)
    best = best[:3]

    rows = [f'<tr><td class="sv-pad" style="padding:22px 24px 0;color:{TXT};font-size:15px;line-height:1.6;">'
            f'The biggest science, space and AI stories of the week, each linked to its source.</td></tr>']
    if top:
        a = top[0]
        rows.append(head("Top stories of the week"))
        if a.get("image"):
            rows.append(f'<tr><td class="sv-pad" style="padding:8px 24px 0;"><a href="{e(a["url"])}"><img src="{e(a["image"])}" alt="" width="552" '
                        f'style="display:block;width:100%;max-width:552px;height:auto;border-radius:8px;border:0;"></a></td></tr>')
        for i, a in enumerate(top, 1):
            rows.append(row(a["title"], a["url"], one_line(a.get("summary")), a.get("source"), i))
    if ai_items:
        rows.append(head("AI this week"))
        rows += [row(a["title"], a["url"], one_line(a.get("summary")), a.get("source")) for a in ai_items]
    if spx or space:
        rows.append(head("Space & launches"))
        if spx: rows.append(row(x_text(spx[0]["text"]), spx[0]["url"], "", "SpaceX on X"))
        rows += [row(a["title"], a["url"], one_line(a.get("summary")), a.get("source")) for a in space]
    if elon or other:
        rows.append(head("Voices on X"))
        if elon: rows.append(xrow("Elon Musk", elon["text"], elon["url"]))
        if other: rows.append(xrow(other[0], other[1]["text"], other[1]["url"]))
    if best:
        rows.append(head("From @SciVigil"))
        rows += [xrow("@SciVigil", p["text"], p.get("url") or f'{XURL}/status/{p["id"]}') for p in best]
    if shorts:
        rows.append(head("Top Shorts"))
        cells = ""
        for s in shorts[:2]:
            u = f'https://www.youtube.com/shorts/{e(s["id"])}'
            cells += (f'<td class="sv-col" width="50%" valign="top" style="padding:6px 6px 0 0;"><a href="{u}">'
                      f'<img src="https://i.ytimg.com/vi/{e(s["id"])}/hqdefault.jpg" alt="" width="260" style="display:block;width:100%;max-width:260px;border-radius:8px;border:0;"></a>'
                      f'<a href="{u}" style="display:block;margin-top:6px;color:{TXT};font-size:14px;font-weight:600;text-decoration:none;">'
                      f'{e(re.sub(r"\s*#shorts", "", s["title"], flags=re.I))}</a></td>')
        if len(shorts[:2]) == 1: cells += '<td class="sv-col" width="50%"></td>'
        rows.append(f'<tr><td class="sv-pad" style="padding:8px 24px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{cells}</tr></table></td></tr>')
    rows.append(f'<tr><td class="sv-pad" style="padding:34px 24px 28px;color:{DIM};font-size:13px;line-height:1.7;text-align:center;border-top:1px solid {LINE};">'
                f'<a href="{SITE}" style="color:{ACC};font-weight:600;">Read more at SciVigilance</a> &middot; updated twice daily<br>'
                f'<a href="{XURL}" style="color:{ACC};font-weight:600;">Follow @SciVigil on X</a></td></tr>')

    style = ('<style>@media only screen and (max-width:620px){.sv-wrap{width:100%!important}.sv-pad{padding-left:16px!important;padding-right:16px!important}'
             '.sv-col{display:block!important;width:100%!important;padding-right:0!important}}</style>')
    content = (style + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{BG}" style="background:{BG};">'
               f'<tr><td align="center" style="padding:16px 0;"><table class="sv-wrap" role="presentation" width="600" cellpadding="0" cellspacing="0" bgcolor="{BG}" '
               f'style="max-width:600px;width:100%;background:{BG};font-family:Helvetica,Arial,sans-serif;">'
               f'<tr><td class="sv-pad" style="padding:22px 24px 0;"><a href="{SITE}" style="color:{TXT};font-size:24px;font-weight:800;text-decoration:none;">'
               f'Sci<span style="color:{ACC};">Vigilance</span></a><div style="color:{DIM};font-size:12px;margin-top:2px;">Weekly digest &middot; {e(latest.get("date", ""))}</div></td></tr>'
               + "".join(rows) + '</table></td></tr></table>')
    n_more = max(0, len(top) - 1) + len(ai_items) + len(space) + (1 if spx else 0)
    subject = f'SciVigilance Weekly: {top[0]["title"] if top else "This week in science"}' + (f' + {n_more} more' if n_more else "")
    preview = one_line(top[0].get("summary"), 140) if top else ""
    return {"subject": subject, "preview_text": preview, "content": content}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out"); ap.add_argument("--json")
    a = ap.parse_args(); d = build()
    if a.out:
        open(a.out, "w", encoding="utf-8").write(
            f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="color-scheme" content="dark light"><title>{e(d["subject"])}</title></head><body style="margin:0;background:{BG};">{d["content"]}</body></html>')
    if a.json: json.dump(d, open(a.json, "w", encoding="utf-8"))
    print(d["subject"])
