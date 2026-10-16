#!/usr/bin/env python3
"""Helper for data/top_stories.json ("Top stories, explained" on the homepage).
The article TEXT must be written by the refresh agent from the FULL source articles (facts only,
attributed, no speculation). This script only helps:
  python3 scripts/top_stories.py candidates   -> ranks stories in data/latest.json (+ featured X) by multi-source coverage
  python3 scripts/top_stories.py check        -> validates data/top_stories.json (schema, 4-6 stories, links resolve)
Schema: {"updated": ISO8601 with offset, "updated_pt": "Oct 16, 2026, 12:00 PM PT",
         "stories": [{"title","tag","date","paragraphs":[...],"sources":[{"name","url","date"?}]}]}"""
import json, os, re, sys, urllib.request, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda f: os.path.join(ROOT, 'data', f)
STOP = set('the a an of to in on for and or with from by is are was be as at its it this that new how why what can could may will after over into than more most first about their they has have just out up'.split())

def words(t): return {w for w in re.findall(r"[a-z0-9][a-z0-9'-]{2,}", t.lower()) if w not in STOP}

def candidates():
    d = json.load(open(D('latest.json')))
    items = d.get('articles', []) + [a for a in d.get('ai', []) if a not in d.get('articles', [])]
    seen, uniq = set(), []
    for a in items:
        if a['url'] in seen: continue
        seen.add(a['url']); uniq.append(a)
    xs = []
    try:
        for acc in json.load(open(D('xfeatured.json')))['accounts']:
            for p in acc['posts']: xs.append((acc['handle'], p.get('url', ''), p['text']))
    except Exception: pass
    rows = []
    for a in uniq:
        k = words(a['title'])
        rel = [b for b in uniq if b is not a and len(k & words(b['title'] + ' ' + b['summary'])) >= 2]
        xr = [h for h, u, t in xs if len(k & words(t)) >= 2]
        rows.append((len({b['source'] for b in rel}) + len(set(xr)), a, rel, xr))
    rows.sort(key=lambda r: (-r[0], r[1]['ts']), reverse=False)
    for score, a, rel, xr in rows[:15]:
        print(f"[{score}] {a['date']} {a['source']}: {a['title']}\n     {a['url']}")
        for b in rel[:4]: print(f"       + {b['source']}: {b['title'][:90]} {b['url']}")
        if xr: print(f"       + X: {', '.join(sorted(set(xr)))}")

def check():
    d = json.load(open(D('top_stories.json'))); ok = True
    st = d.get('stories', [])
    if not 4 <= len(st) <= 6: print('WARN: expected 4-6 stories, got', len(st)); ok = False
    if not d.get('updated') or not d.get('updated_pt'): print('ERR: updated/updated_pt missing'); ok = False
    for s in st:
        for k in ('title', 'date', 'paragraphs', 'sources'):
            if not s.get(k): print('ERR:', s.get('title'), 'missing', k); ok = False
        for src in s.get('sources', []):
            try:
                urllib.request.urlopen(urllib.request.Request(src['url'], headers={'User-Agent': 'Mozilla/5.0'}), timeout=20)
            except Exception as e:
                if 'x.com/' not in src['url']: print('WARN: source not reachable', src['url'], e)
    print('OK' if ok else 'PROBLEMS'); sys.exit(0 if ok else 1)

if __name__ == '__main__':
    {'candidates': candidates, 'check': check}.get((sys.argv[1:] or ['check'])[0], check)()
