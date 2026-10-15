#!/usr/bin/env python3
"""Daily data refresh for SciVigilance.
Writes data/latest.json (real frontier-science news from public RSS feeds; every item keeps
its original link + an image taken from the feed or the article's og:image).
Background images are handled by scripts/update_background.py (hourly pool).
Never invents stories: items without a real link AND real image are skipped."""
import json, os, re, sys, html, datetime, urllib.request, urllib.parse
import feedparser
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
UA = {'User-Agent': 'Mozilla/5.0 (SciVigilance news updater; +https://ciber101.github.io/SciVigilance.github.io/)'}
FEEDS = [  # (source name, feed url, field tag)
 ('NASA', 'https://www.nasa.gov/news-release/feed/', 'Space'),
 ('ESA', 'https://www.esa.int/rssfeed/Our_Activities/Space_Science', 'Space'),
 ('Space.com', 'https://www.space.com/feeds/all', 'Space'),
 ('Phys.org', 'https://phys.org/rss-feed/breaking/', 'Physics'),
 ('ScienceDaily', 'https://www.sciencedaily.com/rss/top/science.xml', 'Science'),
 ('Quanta Magazine', 'https://www.quantamagazine.org/feed/', 'Frontier'),
 ('Science News', 'https://www.sciencenews.org/feed', 'Science'),
 ('New Scientist', 'https://www.newscientist.com/feed/home/', 'Science'),
 ('Live Science', 'https://www.livescience.com/feeds/all', 'Science'),
 ('ScienceAlert', 'https://www.sciencealert.com/feed', 'Science'),
 ('Universe Today', 'https://www.universetoday.com/feed/', 'Space'),
 ('MIT News', 'https://news.mit.edu/rss/research', 'Science'),
]
PER_SOURCE, TOTAL, MAX_AGE_DAYS = 8, 60, 7
AI_FEEDS = [
 ('Hugging Face', 'https://huggingface.co/blog/feed.xml'),
 ('OpenAI', 'https://openai.com/news/rss.xml'),
 ('Google DeepMind', 'https://deepmind.google/blog/rss.xml'),
 ('Simon Willison', 'https://simonwillison.net/atom/everything/'),
 ('Ars Technica', 'https://feeds.arstechnica.com/arstechnica/technology-lab'),
 ('The Verge', 'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml'),
 ('MIT News', 'https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml'),
 ('MarkTechPost', 'https://www.marktechpost.com/feed/'),
 ('MIT Technology Review', 'https://www.technologyreview.com/topic/artificial-intelligence/feed'),
 ('The Decoder', 'https://the-decoder.com/feed/'),
 ('Google AI', 'https://blog.google/technology/ai/rss/'),
]
AI_GOOD = r'\b(model|models|llm|open[- ]weights?|open[- ]source|benchmark|release[sd]?|launch(es|ed)?|gpt[- ]?\d|claude|gemini|gemma|grok|llama|qwen|mistral|deepseek|phi-?\d|gguf|ollama|llama\.cpp|quantiz\w*|reasoning|multimodal|agent\w*|parameters?|context window|fine-?tun\w*|inference|tokens?|transformer|diffusion|anthropic|deepmind|xai|meta ai|hugging ?face)\b'
AI_BAD = r'\b(funding|raises?|valuation|ipo|lawsuit|sues|layoffs?|stock|shares|earnings|revenue|acquisition|acquires|deal|ceo|hiring|policy|regulat\w*|lobby\w*|super bowl|ads?)\b'
AI_TOTAL, AI_MAX_AGE, AI_PER_SOURCE = 30, 14, 5
TAGS = [('Space', r'\b(nasa|esa|mars|moon|lunar|jwst|webb|hubble|galax|star|planet|asteroid|comet|orbit|rocket|telescope|black hole|solar|sun)\w*'),
        ('Physics', r'\b(quantum|particle|physic|cern|collider|laser|photon|neutrino)\w*'),
        ('Biology', r'\b(cell|gene|dna|protein|species|brain|bacteria|virus|evolution|animal|plant)\w*'),
        ('Health', r'\b(cancer|disease|patient|drug|vaccine|medical|health)\w*'),
        ('Earth', r'\b(climate|ocean|earthquake|volcano|glacier|weather|carbon)\w*'),
        ('Tech', r'\b(ai|robot|chip|battery|computer|algorithm)\w*')]

def get(u, n=None):
    r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20)
    return r.read(n) if n else r.read()

def clean(s):
    s = html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))
    return re.sub(r'\s+', ' ', s).strip()

def short(s, n=220):
    if len(s) <= n: return s
    cut = s[:n]; i = max(cut.rfind('. '), -1)
    return cut[:i+1] if i > 120 else cut[:cut.rfind(' ')].rstrip(',;:') + '…'

def feed_image(e):
    for k in ('media_content', 'media_thumbnail'):
        for m in e.get(k, []) or []:
            if m.get('url'): return m['url']
    for l in e.get('links', []):
        if l.get('rel') == 'enclosure' and 'image' in (l.get('type') or 'image'): return l.get('href')
    m = re.search(r'<img[^>]+src="([^"]+)"', (e.get('summary') or '') + ''.join(c.get('value','') for c in e.get('content', [])))
    return m.group(1) if m else None

def og_image(url):
    try:
        page = get(url, 400000).decode('utf-8', 'ignore')
        m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)', page) or \
            re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)', page)
        return html.unescape(m.group(1)) if m else None
    except Exception: return None

def og_desc(url):
    try:
        page = get(url, 400000).decode('utf-8', 'ignore')
        m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:description|description)["\'][^>]+content=["\']([^"\']+)', page) or \
            re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:description|description)', page)
        return clean(m.group(1)) if m else ''
    except Exception: return ''

def _words(t): return {w for w in re.findall(r'[a-z0-9]{4,}', t.lower())}
def dedupe(items):
    # drop the same story covered by two outlets (similar headline+summary or same image file)
    keep = []
    for a in items:
        img = re.sub(r'[-_]?\d+x\d+|\.\w+$', '', a['image'].split('?')[0].rsplit('/', 1)[-1]).lower()
        w = _words(a['title'] + ' ' + a['summary'])
        dup = False
        for b in keep:
            wb = b['_w']
            if (img and img == b['_img']) or (w and len(w & wb) / max(1, min(len(w), len(wb))) > 0.45): dup = True; break
        if not dup: a['_img'], a['_w'] = img, w; keep.append(a)
    for a in keep: a.pop('_img'); a.pop('_w')
    return keep

def tag_for(text, default):
    t = text.lower()
    for name, rx in TAGS:
        if re.search(rx, t): return name
    return default

def news():
    now = datetime.datetime.now(datetime.timezone.utc); out = []; seen = set()
    for src, url, field in FEEDS:
        try: f = feedparser.parse(get(url))
        except Exception as ex: print('feed fail', src, ex, file=sys.stderr); continue
        n = 0
        for e in f.entries:
            if n >= PER_SOURCE: break
            link, title = e.get('link'), clean(e.get('title'))
            if not link or not title or title.lower() in seen or re.match(r'(TB \d|NASA Invites|Media Accreditation)', title): continue
            t = e.get('published_parsed') or e.get('updated_parsed')
            d = datetime.datetime(*t[:6], tzinfo=datetime.timezone.utc) if t else now
            if (now - d).days > MAX_AGE_DAYS: continue
            img = feed_image(e) or og_image(link)
            if not img or not img.startswith('http'): continue
            summ = short(clean(e.get('summary') or ''))
            if len(summ) < 40: continue
            seen.add(title.lower()); n += 1
            out.append({'id': re.sub(r'[^a-z0-9]+', '-', title.lower())[:60].strip('-'), 'title': title, 'summary': summ,
                        'url': link, 'source': src, 'image': img.replace('http://', 'https://').replace('/csz/news/tmb/', '/csz/news/800a/'),
                        'tags': [tag_for(title + ' ' + summ, field)], 'date': d.date().isoformat(), 'ts': d.isoformat()})
        print(src, n)
    out.sort(key=lambda a: a['ts'], reverse=True)
    out = dedupe(out)
    # interleave so one source can't dominate the top of the feed
    res, by = [], {}
    for a in out: by.setdefault(a['source'], []).append(a)
    while any(by.values()) and len(res) < TOTAL:
        for s in sorted(by, key=lambda s: by[s][0]['ts'] if by[s] else '', reverse=True):
            if by[s]: res.append(by[s].pop(0))
    return res[:TOTAL]

def ai_news():
    now = datetime.datetime.now(datetime.timezone.utc); out = []; seen = set()
    for src, url in AI_FEEDS:
        try: f = feedparser.parse(get(url))
        except Exception as ex: print('ai feed fail', src, ex, file=sys.stderr); continue
        n = 0
        for e in f.entries[:40]:
            if n >= AI_PER_SOURCE: break
            link, title = e.get('link'), clean(e.get('title'))
            if not link or not title or title.lower() in seen: continue
            summ = short(clean(e.get('summary') or ''.join(c.get('value', '') for c in e.get('content', []))))
            official = src in ('Hugging Face', 'OpenAI', 'Google DeepMind', 'Google AI')
            if len(summ) < 40 and official and re.search(AI_GOOD, title.lower()): summ = short(og_desc(link))
            text = (title + ' ' + summ).lower()
            if len(re.findall(AI_GOOD, text)) < (1 if official else 2) or re.search(AI_BAD, title.lower()): continue
            t = e.get('published_parsed') or e.get('updated_parsed')
            d = datetime.datetime(*t[:6], tzinfo=datetime.timezone.utc) if t else now
            if (now - d).days > AI_MAX_AGE or len(summ) < 40: continue
            img = feed_image(e) or og_image(link)
            if not img or not img.startswith('http'): continue
            seen.add(title.lower()); n += 1
            out.append({'id': 'ai-' + re.sub(r'[^a-z0-9]+', '-', title.lower())[:56].strip('-'), 'title': title, 'summary': summ,
                        'url': link, 'source': src, 'image': img.replace('http://', 'https://'),
                        'tags': ['AI'], 'date': d.date().isoformat(), 'ts': d.isoformat()})
        print('AI', src, n)
    out.sort(key=lambda a: a['ts'], reverse=True)
    return dedupe(out)[:AI_TOTAL]


if __name__ == '__main__':
    arts = news()
    ai = ai_news()
    if ai:  # mix the 3 newest AI stories into the main feed
        arts = arts[:2] + ai[:1] + arts[2:6] + ai[1:2] + arts[6:10] + ai[2:3] + arts[10:]
    if len(arts) >= 5:
        json.dump({'date': datetime.date.today().isoformat(), 'updated': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='minutes'),
                   'tagline': f'{len(arts)} real stories from the frontier of science, each linked to its source.', 'articles': arts, 'ai': ai},
                  open(os.path.join(DATA, 'latest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    else: print('too few articles; keeping previous latest.json', file=sys.stderr)
    print('articles', len(arts), 'ai', len(ai))
    # Hourly background pool (NASA / ESA / Webb / Hubble / Rubin) — same refresh routine
    try:
        import update_background
        # On routine refreshes, keep the local pool and only refresh APOD + manifest.
        # Full collect runs when the pool is still thin (first setup / recovery).
        man = os.path.join(DATA, 'backgrounds.json')
        n = 0
        if os.path.isfile(man):
            try:
                payload = json.load(open(man, encoding='utf-8'))
                n = payload.get('count') if isinstance(payload, dict) else len(payload or [])
            except Exception:
                n = 0
        if n >= 120:
            rc = update_background.run(skip_collect=True)
        else:
            rc = update_background.run()
        print('update_background exit', rc, 'prior_count', n)
    except Exception as ex:
        print('update_background failed', ex, file=sys.stderr)
