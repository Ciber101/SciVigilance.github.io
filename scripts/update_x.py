#!/usr/bin/env python3
"""Build data/xposts.json from data/x_raw.json (a saved X API v2 response for @SciVigil,
user id 1974272513917267972). X reads need auth, so the raw file is committed and refreshed
by the bot/agent; the daily workflow just rebuilds the display data from it.
Cleans raw t.co links (shown as a 'link' chip instead) and keeps full text (note_tweet when present)."""
import json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw = json.load(open(os.path.join(ROOT, 'data', 'x_raw.json'), encoding='utf-8'))
media = {m['media_key']: m for m in raw.get('includes', {}).get('media', [])}
out = []
for p in raw.get('data', []):
    refs = {r['type'] for r in p.get('referenced_tweets', [])}
    if refs & {'retweeted', 'replied_to'}: continue
    text = (p.get('note_tweet') or {}).get('text') or p['text']
    urls = {u['url']: u.get('expanded_url') for u in p.get('entities', {}).get('urls', [])}
    links = [u for u in re.findall(r'https://t\.co/\w+', text)]
    text = re.sub(r'\s*https://t\.co/\w+', '', text)
    text = re.sub(r'[ \t]+\n', '\n', re.sub(r'\n{3,}', '\n\n', text)).strip()
    imgs = [media[k].get('url') or media[k].get('preview_image_url') for k in p.get('attachments', {}).get('media_keys', []) if k in media]
    out.append({'id': p['id'], 'text': text, 'date': p['created_at'], 'quoted': 'quoted' in refs,
                'link': next((urls.get(l) or l for l in links if 'x.com' not in (urls.get(l) or '')), None),
                'image': next((i for i in imgs if i), None),
                'truncated': not re.search(r'[.!?)"\u2019\u201d]$|#\w+$', text),
                'url': 'https://x.com/SciVigil/status/' + p['id']})
json.dump({'handle': 'SciVigil', 'name': 'Science in 280', 'posts': out[:6]},
          open(os.path.join(ROOT, 'data', 'xposts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('xposts', len(out[:6]))
