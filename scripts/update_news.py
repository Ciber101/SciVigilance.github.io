#!/usr/bin/env python3
"""Daily data refresh for SciVigilance.
Writes data/latest.json (real frontier-science news from public RSS feeds; every item keeps
its original link + an image taken from the feed or the article's og:image) and
data/backgrounds.json (public-domain NASA space imagery that rotates daily).
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
]
PER_SOURCE, TOTAL, MAX_AGE_DAYS = 3, 18, 7
AI_FEEDS = [
 ('Hugging Face', 'https://huggingface.co/blog/feed.xml'),
 ('OpenAI', 'https://openai.com/news/rss.xml'),
 ('Google DeepMind', 'https://deepmind.google/blog/rss.xml'),
 ('Simon Willison', 'https://simonwillison.net/atom/everything/'),
 ('Ars Technica', 'https://feeds.arstechnica.com/arstechnica/technology-lab'),
 ('The Verge', 'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml'),
 ('MIT News', 'https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml'),
 ('MarkTechPost', 'https://www.marktechpost.com/feed/'),
]
AI_GOOD = r'\b(model|models|llm|open[- ]weights?|open[- ]source|benchmark|release[sd]?|launch(es|ed)?|gpt[- ]?\d|claude|gemini|gemma|grok|llama|qwen|mistral|deepseek|phi-?\d|gguf|ollama|llama\.cpp|quantiz\w*|reasoning|multimodal|agent\w*|parameters?|context window|fine-?tun\w*|inference|tokens?|transformer|diffusion|anthropic|deepmind|xai|meta ai|hugging ?face)\b'
AI_BAD = r'\b(funding|raises?|valuation|ipo|lawsuit|sues|layoffs?|stock|shares|earnings|revenue|acquisition|acquires|deal|ceo|hiring|policy|regulat\w*|lobby\w*|super bowl|ads?)\b'
AI_TOTAL, AI_MAX_AGE = 9, 14
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
        for e in f.entries[:25]:
            if n >= 2: break
            link, title = e.get('link'), clean(e.get('title'))
            if not link or not title or title.lower() in seen: continue
            summ = short(clean(e.get('summary') or ''.join(c.get('value', '') for c in e.get('content', []))))
            official = src in ('Hugging Face', 'OpenAI', 'Google DeepMind')
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
    return out[:AI_TOTAL]

BG_IDS = [  # hand-picked real public-domain NASA space imagery (no ground/lab photos, no artist concepts)
 'PIA04921', 'PIA15985', 'PIA18164', 'PIA23122', 'PIA03606', 'PIA12348', 'PIA22568', 'PIA17563',
 'PIA09579', 'PIA04230', 'PIA14417', 'PIA20061', 'PIA18906', 'PIA21923']

def nasa_asset(i):
    meta = json.loads(get('https://images-api.nasa.gov/search?nasa_id=' + urllib.parse.quote(i)))['collection']['items']
    title = meta[0]['data'][0]['title'] if meta else i
    hrefs = [x['href'] for x in json.loads(get('https://images-api.nasa.gov/asset/' + urllib.parse.quote(i)))['collection']['items']]
    pick = next((h for k in ('~large.jpg', '~medium.jpg') for h in hrefs if h.endswith(k)), None)
    return {'image': pick.replace('http://', 'https://'), 'credit': f'{title} — NASA (public domain)',
            'credit_url': 'https://images.nasa.gov/details/' + i} if pick else None

def backgrounds():
    slides = []
    try:
        a = json.loads(get('https://api.nasa.gov/planetary/apod?api_key=' + os.environ.get('NASA_API_KEY', 'DEMO_KEY')))
        img = a.get('hdurl') or a.get('url') or ''
        if a.get('media_type') == 'image' and not a.get('copyright') and 'apod.nasa.gov' in img and img.lower().endswith(('.jpg', '.jpeg', '.png')):
            slides.append({'image': (a.get('hdurl') or a['url']).replace('http://', 'https://'),
                           'credit': f"APOD {a['date']}: {a['title']} — NASA (public domain)",
                           'credit_url': 'https://apod.nasa.gov/apod/astropix.html'})
    except Exception as ex: print('APOD skip', ex, file=sys.stderr)
    day = datetime.date.today().toordinal()
    for k in range(len(BG_IDS)):
        if len(slides) >= 4: break
        try:
            s = nasa_asset(BG_IDS[(day + k) % len(BG_IDS)])
            if s: slides.append(s)
        except Exception as ex: print('bg fail', ex, file=sys.stderr)
    return slides

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
    bg = backgrounds()
    if bg: json.dump(bg, open(os.path.join(DATA, 'backgrounds.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('articles', len(arts), 'backgrounds', len(bg))
