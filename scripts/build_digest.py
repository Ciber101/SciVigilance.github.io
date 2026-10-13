#!/usr/bin/env python3
"""Build the SciVigilance Weekly email digest from the site's data files.

Usage: python3 scripts/build_digest.py [--out digest.html] [--json meta.json]
Only real data from data/*.json is used. Kit's template adds the mailing
address and unsubscribe footer automatically.
"""
import argparse, html, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://ciber101.github.io/SciVigilance.github.io/"
ACC, TXT, DIM, BG, CARD = "#f5a623", "#e8ecf4", "#9aa4b8", "#0b0e17", "#141927"

def load(name, default):
    try:
        with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

e = lambda s: html.escape(str(s or ""), quote=True)

def item(a):
    return (f'<tr><td style="padding:10px 0;border-bottom:1px solid #232a3d;">'
            f'<a href="{e(a["url"])}" style="color:{TXT};font-weight:600;text-decoration:none;font-size:15px;">{e(a["title"])}</a>'
            f'<div style="color:{DIM};font-size:13px;line-height:1.5;margin-top:4px;">{e(a.get("summary",""))}</div>'
            f'<div style="color:{ACC};font-size:12px;margin-top:4px;">{e(a.get("source",""))}</div></td></tr>')

def section(title, body):
    return (f'<tr><td style="padding:28px 24px 0;"><div style="color:{ACC};font-size:12px;letter-spacing:2px;'
            f'text-transform:uppercase;font-weight:700;margin-bottom:6px;">{e(title)}</div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{body}</table></td></tr>')

def build():
    latest = load("latest.json", {})
    arts, ai = latest.get("articles", []), latest.get("ai", [])
    shorts = load("shorts.json", {}).get("shorts", [])
    xposts = load("x_raw.json", {}).get("data", [])

    top = next((a for a in arts if a.get("image")), arts[0] if arts else None)
    rest = [a for a in arts if a is not top]
    space = [a for a in rest if set(a.get("tags", [])) & {"Space", "Physics"}][:3]
    ai3 = ai[:3] or [a for a in rest if "AI" in a.get("tags", [])][:3]
    n_more = len(space) + len(ai3)

    rows = [f'<tr><td style="padding:28px 24px 0;color:{TXT};font-size:15px;line-height:1.6;">'
            f'Here are this week\'s top stories from SciVigilance, each linked to its original source.</td></tr>']
    if top:
        img = (f'<a href="{e(top["url"])}"><img src="{e(top["image"])}" alt="" width="552" '
               f'style="display:block;width:100%;max-width:552px;height:auto;border-radius:8px;border:0;"></a>') if top.get("image") else ""
        rows.append(section("Top story", f'<tr><td>{img}<a href="{e(top["url"])}" style="display:block;margin-top:14px;'
            f'color:{TXT};font-size:20px;font-weight:700;line-height:1.3;text-decoration:none;">{e(top["title"])}</a>'
            f'<p style="color:{DIM};font-size:14px;line-height:1.6;margin:8px 0;">{e(top.get("summary",""))}</p>'
            f'<a href="{e(top["url"])}" style="color:{ACC};font-size:14px;font-weight:600;">Read at {e(top.get("source","source"))} &rarr;</a></td></tr>'))
    if ai3: rows.append(section("AI this week", "".join(map(item, ai3))))
    if space: rows.append(section("Space & physics", "".join(map(item, space))))
    if shorts:
        s = shorts[0]; u = f'https://www.youtube.com/shorts/{e(s["id"])}'
        rows.append(section("Short of the week", f'<tr><td><a href="{u}"><img src="https://i.ytimg.com/vi/{e(s["id"])}/hqdefault.jpg" alt="" width="280" '
            f'style="display:block;width:280px;max-width:100%;border-radius:8px;border:0;"></a>'
            f'<a href="{u}" style="display:block;margin-top:8px;color:{TXT};font-weight:600;text-decoration:none;">{e(re.sub(r"\s*#shorts","",s["title"],flags=re.I))}</a></td></tr>'))
    if xposts:
        p = xposts[0]; t = re.sub(r"https://t\.co/\S+", "", p.get("text", "")).strip()
        rows.append(section("From @SciVigil", f'<tr><td style="background:{CARD};border-left:3px solid {ACC};padding:14px 16px;'
            f'color:{TXT};font-size:14px;line-height:1.6;">{e(t).replace(chr(10),"<br>")}'
            f'<div style="margin-top:8px;"><a href="{e(p.get("url"))}" style="color:{ACC};font-size:13px;">View on X &rarr;</a></div></td></tr>'))
    rows.append(f'<tr><td style="padding:32px 24px;color:{DIM};font-size:13px;line-height:1.6;text-align:center;">'
        f'More stories, updated twice daily, at <a href="{SITE}" style="color:{ACC};">SciVigilance</a>.<br>'
        f'Know someone who\'d like this? Forward it along.</td></tr>')

    content = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};">'
        f'<tr><td align="center" style="padding:20px 0;"><table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        f'style="max-width:600px;width:100%;background:{BG};font-family:Helvetica,Arial,sans-serif;">'
        f'<tr><td style="padding:24px 24px 0;"><a href="{SITE}" style="color:{TXT};font-size:22px;font-weight:800;text-decoration:none;">'
        f'Sci<span style="color:{ACC};">Vigilance</span></a><div style="color:{DIM};font-size:12px;">Weekly digest &middot; {e(latest.get("date",""))}</div></td></tr>'
        + "".join(rows) + '</table></td></tr></table>')
    subject = f'SciVigilance Weekly: {top["title"] if top else "This week in science"}' + (f' + {n_more} more' if n_more else '')
    preview = (top.get("summary", "") if top else "")[:140]
    return {"subject": subject, "preview_text": preview, "content": content}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out"); ap.add_argument("--json")
    a = ap.parse_args(); d = build()
    if a.out: open(a.out, "w", encoding="utf-8").write(f'<!doctype html><html><head><meta charset="utf-8"><title>{e(d["subject"])}</title></head><body style="margin:0;background:{BG};">{d["content"]}</body></html>')
    if a.json: json.dump(d, open(a.json, "w", encoding="utf-8"))
    print(d["subject"])
