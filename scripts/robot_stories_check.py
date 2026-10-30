#!/usr/bin/env python3
"""Validate an "X, explained" file: data/robot_stories.json (default), data/science_stories.json or data/ai_stories.json
   usage: python3 scripts/robot_stories_check.py [data/science_stories.json]
Optional per story: "image": {"url": https source image, "credit": who made it, "alt"}. Same shape as top_stories.json (no audio):
{updated (ISO), updated_pt, stories:[{title, tag, date YYYY-MM-DD, paragraphs:[2-4 str], sources:[{name,url,date}]}]} with 3-6 stories.
Checks schema, https links reachable (x.com links are format-checked only), and blocks known paywalled domains."""
import json, os, re, sys, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYWALLED = ('the-decoder.com', 'theverge.com', 'technologyreview.com', 'newscientist.com', 'wsj.com', 'ft.com', 'bloomberg.com',
             'nytimes.com', 'economist.com', 'theinformation.com', 'interestingengineering.com', 'businessinsider.com', 'washingtonpost.com')
FILE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'data', 'robot_stories.json')
d = json.load(open(FILE, encoding='utf-8'))
err = []
st = d.get('stories') or []
if not d.get('updated') or not d.get('updated_pt'): err.append('missing updated/updated_pt')
if not 1 <= len(st) <= 6: err.append(f'need 1-6 stories, have {len(st)}')
for i, s in enumerate(st):
    for k in ('title', 'tag', 'date', 'paragraphs', 'sources'):
        if not s.get(k): err.append(f'story {i}: missing {k}')
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', s.get('date', '')): err.append(f'story {i}: bad date')
    if not 1 <= len(s.get('paragraphs', [])) <= 4: err.append(f'story {i}: 1-4 paragraphs')
    im = s.get('image')
    if im is not None and (not str(im.get('url', '')).startswith('https://') or not im.get('credit')): err.append(f'story {i}: image needs https url + credit')
    if re.search('[\u00c3\u00c2\ufffd]|\u00e2\u20ac', json.dumps(s, ensure_ascii=False)): err.append(f'story {i}: garbled characters')
    for x in s.get('sources', []):
        u = x.get('url', '')
        if not u.startswith('https://') or not x.get('name'): err.append(f'story {i}: bad source {x}'); continue
        if any(p in u for p in PAYWALLED): err.append(f'story {i}: paywalled source {u}')
        if re.match(r'https://x\.com/\w+/status/\d+$', u): continue
        try:
            urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 (SciVigilance check)'}), timeout=20)
        except Exception as e: err.append(f'story {i}: unreachable {u} ({e})')
_bp = os.path.join(ROOT, 'data', 'blocklist.json')  # off-topic stories marc ruled out
if os.path.exists(_bp):
    _b = json.load(open(_bp, encoding='utf-8')); _t = [t.lower() for t in _b.get('terms', []) + _b.get('urls', [])]
    for i, s in enumerate(st):
        _blob = json.dumps(s, ensure_ascii=False).lower()
        err += [f'story {i}: blocklisted ({t}), see data/blocklist.json' for t in _t if t in _blob]
print('\n'.join(err) if err else f'OK: {len(st)} stories in {os.path.basename(FILE)}')
sys.exit(1 if err else 0)
