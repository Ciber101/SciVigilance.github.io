#!/usr/bin/env python3
"""Refresh data/shorts.json from the channel's public RSS feed (no auth). Only /shorts/ links are kept,
so regular (non-Short) uploads never appear. Keeps previously known Shorts if the feed is unavailable."""
import json, os, urllib.request, xml.etree.ElementTree as ET
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH = 'UCZudcvU912vRNYnb1lCzAdw'
OUT = os.path.join(ROOT, 'data', 'shorts.json')
old = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {'shorts': []}
ns = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}
try:
    xml = urllib.request.urlopen(urllib.request.Request('https://www.youtube.com/feeds/videos.xml?channel_id=' + CH, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20).read()
    shorts = []
    for e in ET.fromstring(xml).findall('a:entry', ns):
        link = e.find('a:link', ns).get('href', '')
        if '/shorts/' not in link: continue
        shorts.append({'id': e.find('yt:videoId', ns).text, 'title': e.find('a:title', ns).text, 'date': e.find('a:published', ns).text})
    known = {s['id'] for s in shorts}
    shorts += [s for s in old.get('shorts', []) if s['id'] not in known]
except Exception as ex:
    print('feed fail', ex); shorts = old.get('shorts', [])
json.dump({'channel': 'https://www.youtube.com/@ciberaifacts', 'shorts': shorts}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('shorts', len(shorts))
