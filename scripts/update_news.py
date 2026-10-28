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
# RULE: no paywalled/metered sources (marc, Oct 18 2026). Removed: New Scientist, The Verge, MIT Tech Review, The Decoder.
FEEDS = [  # (source name, feed url, field tag)
 ('NASA', 'https://www.nasa.gov/news-release/feed/', 'Space'),
 ('ESA', 'https://www.esa.int/rssfeed/Our_Activities/Space_Science', 'Space'),
 ('Space.com', 'https://www.space.com/feeds.xml', 'Space'),
 ('Phys.org', 'https://phys.org/rss-feed/breaking/', 'Physics'),
 ('ScienceDaily', 'https://www.sciencedaily.com/rss/top/science.xml', 'Science'),
 ('Quanta Magazine', 'https://www.quantamagazine.org/feed/', 'Frontier'),
 ('Science News', 'https://www.sciencenews.org/feed', 'Science'),
 ('Live Science', 'https://www.livescience.com/feeds.xml', 'Science'),
 ('ScienceAlert', 'https://www.sciencealert.com/feed', 'Science'),
 ('Universe Today', 'https://www.universetoday.com/feed/', 'Space'),
 ('MIT News', 'https://news.mit.edu/rss/research', 'Science'),
 ('NASA JPL', 'https://www.jpl.nasa.gov/feeds/news/', 'Space'),
 ('The Conversation', 'https://theconversation.com/us/technology/articles.atom', 'Science'),
 ('Nature Communications', 'https://www.nature.com/ncomms.rss', 'Science'),
]
PER_SOURCE, TOTAL, MAX_AGE_DAYS = 8, 60, 7
AI_FEEDS = [
 ('Hugging Face', 'https://huggingface.co/blog/feed.xml'),
 ('OpenAI', 'https://openai.com/news/rss.xml'),
 ('Google DeepMind', 'https://deepmind.google/blog/rss.xml'),
 ('Simon Willison', 'https://simonwillison.net/atom/everything/'),
 ('Ars Technica', 'https://feeds.arstechnica.com/arstechnica/technology-lab'),
 ('MIT News', 'https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml'),
 ('MarkTechPost', 'https://www.marktechpost.com/feed/'),
 ('Google AI', 'https://blog.google/technology/ai/rss/'),
 ('Qwen', 'https://qwenlm.github.io/blog/index.xml'),
 ('Google Research', 'https://research.google/blog/rss/'),
 ('Microsoft Research', 'https://www.microsoft.com/en-us/research/feed/'),
 ('NVIDIA', 'https://blogs.nvidia.com/feed/'),
]
AI_GOOD = r'\b(model|models|llm|open[- ]weights?|open[- ]source|benchmark|release[sd]?|launch(es|ed)?|gpt[- ]?\d|claude|gemini|gemma|grok|llama|qwen|mistral|deepseek|phi-?\d|gguf|ollama|llama\.cpp|quantiz\w*|reasoning|multimodal|agent\w*|parameters?|context window|fine-?tun\w*|inference|tokens?|transformer|diffusion|anthropic|deepmind|xai|meta ai|hugging ?face)\b'
AI_BAD = r'\b(funding|raises?|valuation|ipo|lawsuit|sues|layoffs?|stock|shares|earnings|revenue|acquisition|acquires|deal|ceo|hiring|policy|regulat\w*|lobby\w*|super bowl|ads?)\b'
AI_TOTAL, AI_MAX_AGE, AI_PER_SOURCE = 36, 14, 5
TAGS = [('Space', r'\b(nasa|esa|jaxa|isro|mars|martian|moons?|lunar|jwst|webb|hubble|galax\w*|stars?|starbirth|stellar|planet\w*|exoplanet\w*|asteroids?|comets?|orbit\w*|rockets?|telescopes?|black holes?|solar system|sun|spacecraft|spacewalk\w*|astronom\w*|astronauts?|cosmic|cosmolog\w*|universe|nebula\w*|neptune|jupiter|saturn|io|ganymede|artemis)\b'),
        ('Physics', r'\b(quantum|particles?|physics|physicists?|cern|collider|lasers?|photons?|neutrinos?|atoms?|atomic|magnet\w*|superconduct\w*|molecules?|chemists?|chemistry)\b'),
        ('Biology', r'\b(cells?|genes?|genetic\w*|dna|proteins?|species|brains?|bacteri\w*|virus\w*|evolution\w*|animals?|plants?|fung\w*|ants?|insects?|flamingos?|salamanders?|tigers?|parasites?|fossils?|dinosaurs?|denisovans?|neanderthals?|ancestors?|archaeolog\w*|biodiversity|microbes?|ecolog\w*)\b'),
        ('Health', r'\b(cancer|disease\w*|patients?|drugs?|vaccines?|medical|health|death|mortality|implants?|autis\w*|hepatitis|infect\w*|cdc|neurons?|inflammation)\b'),
        ('Earth', r'\b(climate|oceans?|earthquakes?|volcan\w*|glaciers?|ice ages?|icebergs?|permafrost|frozen ground|weather|carbon|tibetan plateau|forests?)\b'),
        ('Tech', r'\b(chips?|batter(y|ies)|computers?|algorithms?|origami|materials?|engineering)\b')]
# Science feed (homepage Daily Signal + news.html) is science only: AI and robot stories have their own sections.
NOT_SCIENCE = r'\b(ai|a\.i\.|artificial intelligence|chatgpt|chatbots?|llms?|large language models?|machine learning|openai|anthropic|robots?|robotics|humanoids?|data cent(er|re)s?|trailers?|movies?|films?|tv|netflix|episode|php|websites?|software|campaign ads?|votes?|voters?|elections?|homelessness|deals?|sales?|black friday)\b'

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

# Natural sciences only (marc, Oct 28 2026): no social science / policy / economics / law / rights / education / "science of everyday things".
NOT_NATURAL = r'\b(human rights|rights|treaty|treaties|un|united nations|law|laws|legal|court|policy|policies|politic\w*|government|congress|homeless\w*|poverty|econom\w*|jobs?|employment|wages?|education|schools?|students?|teachers?|universit(y|ies)|colleges?|evaluation|j-pal|social|society|sociolog\w*|psycholog\w*|memor(y|ies)|grief|dead people|religio\w*|culture|cultural|history of|museums?|roller coasters?|sports?|football|nfl|games?|toys?|fashion|food|recipes?|architect\w*|construction|voting|klein bottle|mathemat\w*|ceos?|business|market\w*|investors?|startups?|mentors?|talent|careers?|made me feel|workforce|interns?\b)\b'

def tag_for(text, default, title=''):
    """Best-scoring topic (title hits count 3x); the feed's own field breaks ties, so 'starvation' or 'Phys.org' alone can't misfile a story."""
    t, ti = text.lower(), title.lower()
    score = {name: len(re.findall(rx, t)) + 2 * len(re.findall(rx, ti)) for name, rx in TAGS}
    best = max(score.values())
    if best == 0: return default
    if score.get(default, 0) == best: return default
    return max(score, key=lambda k: score[k])

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
            if re.search(NOT_SCIENCE, title.lower()) or re.search(NOT_NATURAL, title.lower()): continue
            if not any(re.search(rx, (title + ' ' + summ).lower()) for n_, rx in TAGS if n_ != 'Tech'): continue  # must be natural science  # AI / robot stories belong to their own sections
            seen.add(title.lower()); n += 1
            out.append({'id': re.sub(r'[^a-z0-9]+', '-', title.lower())[:60].strip('-'), 'title': title, 'summary': summ,
                        'url': link, 'source': src, 'image': img.replace('http://', 'https://').replace('/csz/news/tmb/', '/csz/news/800a/'),
                        'tags': [tag_for(title + ' ' + summ, field, title)], 'date': d.date().isoformat(), 'ts': d.isoformat()})
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
    return dedupe(out)


# ---- Frontier-lab + open-weight sources without RSS (all free, official pages) ----
PAGE_SOURCES = [  # (source, index url, link regex, base) — newest links appear first on these pages
 ('Anthropic', 'https://www.anthropic.com/news', r'href="(/news/[a-z0-9-]+)"', 'https://www.anthropic.com'),
 ('xAI', 'https://x.ai/news', r'href="(/news/[a-z0-9-]+)"', 'https://x.ai'),
 ('DeepSeek', 'https://api-docs.deepseek.com/news/news', r'href="(/news/news\d{6})"', 'https://api-docs.deepseek.com'),
 ('Mistral AI', 'https://mistral.ai/news/', r'href="((?:https://mistral\.ai)?/news/[a-z0-9-]+/?)"', 'https://mistral.ai'),
 ('Meta AI', 'https://ai.meta.com/blog/', r'href="(https://ai\.meta\.com/blog/[a-z0-9-]+/)"', ''),
 ('Ollama', 'https://ollama.com/blog', r'href="(/blog/[a-z0-9-]+)"', 'https://ollama.com'),
]
HF_ORGS = [  # (source label, HF org) — new model repos = release signal
 ('DeepSeek', 'deepseek-ai'), ('Qwen', 'Qwen'), ('Moonshot AI (Kimi)', 'moonshotai'), ('Zhipu AI (GLM)', 'zai-org'),
 ('MiniMax', 'MiniMaxAI'), ('ByteDance Seed', 'ByteDance-Seed'), ('Mistral AI', 'mistralai'), ('Meta Llama', 'meta-llama'),
 ('OpenAI', 'openai'), ('Google (Gemma)', 'google'), ('xAI', 'xai-org'),
]
FRONTIER_SRC = {'Anthropic', 'OpenAI', 'xAI', 'Google DeepMind', 'Google AI', 'Google Research', 'DeepSeek', 'Qwen',
                'Moonshot AI (Kimi)', 'Zhipu AI (GLM)', 'MiniMax', 'ByteDance Seed', 'Google (Gemma)'}
FRONTIER_KW = r'\b(google|anthropic|claude|openai|chatgpt|gpt-?\d|codex|sora|xai|grok|deepmind|gemini|deepseek|qwen|alibaba|moonshot|kimi|zhipu|glm-?\d|z\.ai|minimax|bytedance|doubao|seed-?\d)\b'
LOCAL_SRC = {'Hugging Face', 'Ollama', 'Mistral AI', 'Meta Llama', 'Meta AI', 'Simon Willison'}
LOCAL_KW = r'\b(open (model|models)|open[- ]weights?|open[- ]source|gguf|ollama|llama\.cpp|quantiz\w*|run(s|ning)? locally|local (llm|model)s?|on[- ]device|hugging ?face|mistral|llama|gemma|phi-?\d)\b'

def meta(page, *names):
    for n in names:
        m = re.search(r'<meta[^>]+(?:property|name|itemprop)=["\']%s["\'][^>]+content=["\']([^"\']+)' % n, page) or \
            re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name|itemprop)=["\']%s["\']' % n, page)
        if m: return html.unescape(m.group(1))
    return ''

def page_news(sources=None, tag='AI', max_age=None):
    now = datetime.datetime.now(datetime.timezone.utc); out = []
    max_age = max_age or AI_MAX_AGE
    for src, idx, rx, base in (sources or PAGE_SOURCES):
        try: links = list(dict.fromkeys(re.findall(rx, get(idx).decode('utf-8', 'ignore'))))[:6]
        except Exception as ex: print('page fail', src, ex, file=sys.stderr); continue
        n = 0
        for l in links:
            url = l if l.startswith('http') else base + l
            if url.rstrip('/') == idx.rstrip('/'): continue
            try: page = get(url, 600000).decode('utf-8', 'ignore')
            except Exception: continue
            title = clean(meta(page, 'og:title') or (re.search(r'<title>(.*?)</title>', page, re.S) or [None, ''])[1])
            title = re.sub(r'\s*[|\-–]\s*(Anthropic|xAI|Boston Dynamics|Mistral AI|Mistral|Meta AI|Ollama.*|DeepSeek.*)$', '', title)
            summ = short(clean(meta(page, 'og:description', 'description')))
            img = meta(page, 'og:image', 'twitter:image')
            ds = meta(page, 'article:published_time', 'datePublished') or \
                 (re.search(r'"datePublished"\s*:\s*"([^"]+)"', page) or [None, ''])[1]
            d = None
            try: d = datetime.datetime.fromisoformat(ds.replace('Z', '+00:00')) if ds else None
            except Exception: d = None
            m = re.search(r'news(\d{2})(\d{2})(\d{2})$', url)
            if not d and m: d = datetime.datetime(2000 + int(m[1]), int(m[2]), int(m[3]), tzinfo=datetime.timezone.utc)
            if d and d.tzinfo is None: d = d.replace(tzinfo=datetime.timezone.utc)
            if not d or (now - d).days > max_age or not title or len(summ) < 40: continue
            if not img or not img.startswith('http'): continue
            out.append({'id': 'ai-' + re.sub(r'[^a-z0-9]+', '-', title.lower())[:56].strip('-'), 'title': title, 'summary': summ,
                        'url': url, 'source': src, 'image': img, 'tags': [tag], 'date': d.date().isoformat(), 'ts': d.isoformat()})
            n += 1
            if n >= 3: break
        print('AI page', src, n)
    return out

def hf_releases():
    now = datetime.datetime.now(datetime.timezone.utc); out = []
    for src, org in HF_ORGS:
        try: ms = json.loads(get(f'https://huggingface.co/api/models?author={org}&sort=createdAt&direction=-1&limit=8'))
        except Exception as ex: print('hf fail', org, ex, file=sys.stderr); continue
        n = 0
        for m in ms:
            d = datetime.datetime.fromisoformat(m['createdAt'].replace('Z', '+00:00'))
            if (now - d).days > 7 or n >= 2: continue
            name = m['id'].split('/', 1)[1]
            if re.search(r'(-GGUF|-AWQ|-GPTQ|-FP8|-Int[48]|-MLX|-bnb|-4bit|-8bit)$', name, re.I): continue  # skip quantized duplicates
            url = 'https://huggingface.co/' + m['id']
            task = (m.get('pipeline_tag') or 'model').replace('-', ' ')
            lic = next((t.split(':', 1)[1] for t in m.get('tags', []) if t.startswith('license:')), '')
            summ = f"{src} published a new {task} model, {name}, on Hugging Face" + (f" under the {lic} license" if lic else '') + '. Weights and model card are free to view.'
            out.append({'id': 'ai-hf-' + re.sub(r'[^a-z0-9]+', '-', m['id'].lower())[:52], 'title': f'{src} releases {name} on Hugging Face',
                        'summary': summ, 'url': url, 'source': src, 'image': f'https://cdn-thumbnails.huggingface.co/social-thumbnails/models/{m["id"]}.png',
                        'tags': ['AI'], 'date': d.date().isoformat(), 'ts': d.isoformat(), 'kind': 'release'})
            n += 1
        print('AI hf', src, n)
    return out

def ai_tier(a, now):
    age_h = (now - datetime.datetime.fromisoformat(a['ts'])).total_seconds() / 3600
    t = a['title'].lower()
    frontier = a['source'] in FRONTIER_SRC or re.search(FRONTIER_KW, t)
    local = a['source'] in LOCAL_SRC or re.search(LOCAL_KW, t)
    if frontier and age_h <= 48: return 0
    if local and age_h <= 72: return 1
    return 2

def rank_ai(items):
    """Frontier-lab items from the last 48h first (newest first), then open-weight/local items from the last 72h,
    then everything else newest first."""
    now = datetime.datetime.now(datetime.timezone.utc)
    for a in items: a['rank'] = ai_tier(a, now)
    items.sort(key=lambda a: a['ts'], reverse=True)
    items.sort(key=lambda a: a['rank'])
    return items

# ---- Robots (free sources only; verified no paywall Oct 19 2026) ----
ROBOT_FEEDS = [
 ('IEEE Spectrum', 'https://spectrum.ieee.org/feeds/topic/robotics.rss'),
 ('The Robot Report', 'https://www.therobotreport.com/feed/'),
 ('Robohub', 'https://robohub.org/feed/'),
 ('TechCrunch', 'https://techcrunch.com/category/robotics/feed/'),
 ('New Atlas', 'https://newatlas.com/robotics/index.rss'),
 ('NVIDIA', 'https://blogs.nvidia.com/blog/category/robotics/feed/'),
]
ROBOT_PAGES = [
 ('Figure', 'https://www.figure.ai/news', r'href="(/news/[a-z0-9-]+)"', 'https://www.figure.ai'),
 ('Boston Dynamics', 'https://bostondynamics.com/blog/', r'href="(https://bostondynamics\.com/blog/[a-z0-9-]+/)"', ''),
 ('1X', 'https://www.1x.tech/discover', r'href="(/discover/[a-z0-9-]+)"', 'https://www.1x.tech'),
 ('Agility Robotics', 'https://www.agilityrobotics.com/content', r'href="(/content/[a-z0-9-]+)"', 'https://www.agilityrobotics.com'),
]
ROBOT_TOTAL, ROBOT_MAX_AGE, ROBOT_PER_SOURCE = 30, 21, 6
HUMANOID_SRC = {'Figure', 'Boston Dynamics', '1X', 'Agility Robotics'}
HUMANOID_KW = r'\b(humanoid\w*|figure ?0?\d|figure ai|optimus|tesla bot|1x|neo|boston dynamics|atlas|agility|digit|apptronik|apollo|unitree|ubtech|walker s?\d*|agibot|fourier|xpeng|iron robot|sanctuary|phoenix|galbot|leju|engine ?ai|kepler|booster robotics|gr00t)\b'
ROBOT_OK = r'\b(robot\w*|humanoid\w*|automat\w*|drone\w*|autonomous|exoskeleton\w*|gripper\w*|actuator\w*|manipulat\w*|embodied|physical ai|cobot\w*|amr\w*|isaac|gr00t)\b'

# Robots section = robots only: needs a real robot word ("autonomous agents", "edge AI", "automation" alone are not enough)
ROBOT_STRONG = r'\b(robot\w*|humanoid\w*|drones?|exoskeleton\w*|grippers?|cobots?|quadrupeds?|legged|bipeds?|embodied|physical ai|optimus|gr00t|robo\w*|bots?|self-driving|driverless|autonomous (vehicles?|driving|cars?|trucks?|equipment|heavy equipment))\b'
NOT_ROBOT = r'\b(award|nominations?|acquires?|acquire|acquisition)\b'

def robot_news():
    now = datetime.datetime.now(datetime.timezone.utc); out = []; seen = set()
    for src, url in ROBOT_FEEDS:
        try: f = feedparser.parse(get(url))
        except Exception as ex: print('robot feed fail', src, ex, file=sys.stderr); continue
        n = 0
        for e in f.entries[:40]:
            if n >= ROBOT_PER_SOURCE: break
            link, title = e.get('link'), clean(e.get('title'))
            if not link or not title or title.lower() in seen: continue
            summ = short(clean(e.get('summary') or ''.join(c.get('value', '') for c in e.get('content', []))))
            if len(summ) < 40: summ = short(og_desc(link))
            if not re.search(ROBOT_STRONG, (title + ' ' + summ).lower()) or re.search(r'\b(podcast|webinar|sponsored|register now)\b', title.lower()): continue
            t = e.get('published_parsed') or e.get('updated_parsed')
            d = datetime.datetime(*t[:6], tzinfo=datetime.timezone.utc) if t else now
            if (now - d).days > ROBOT_MAX_AGE or len(summ) < 40: continue
            img = feed_image(e) or og_image(link)
            if not img or not img.startswith('http'): continue
            seen.add(title.lower()); n += 1
            out.append({'id': 'rb-' + re.sub(r'[^a-z0-9]+', '-', title.lower())[:56].strip('-'), 'title': title, 'summary': summ,
                        'url': link, 'source': src, 'image': img.replace('http://', 'https://'),
                        'tags': ['Robots'], 'date': d.date().isoformat(), 'ts': d.isoformat()})
        print('Robots', src, n)
    have = {a['url'] for a in out}
    out += [a for a in page_news(ROBOT_PAGES, 'Robots', 60) if a['url'] not in have]
    for a in out: a['id'] = a['id'].replace('ai-', 'rb-', 1)
    out = [a for a in out if re.search(ROBOT_STRONG, (a['title'] + ' ' + a['summary']).lower()) and not re.search(NOT_ROBOT, a['title'].lower())]
    return rank_robots(dedupe(sorted(out, key=lambda a: a['ts'], reverse=True)))[:ROBOT_TOTAL]

def rank_robots(items):
    """Humanoid/frontier-robot company news from the last 4 days first (newest first), then everything else newest first."""
    now = datetime.datetime.now(datetime.timezone.utc)
    for a in items:
        age_h = (now - datetime.datetime.fromisoformat(a['ts'])).total_seconds() / 3600
        hum = a['source'] in HUMANOID_SRC or re.search(HUMANOID_KW, a['title'].lower())
        a['rank'] = 0 if hum and age_h <= 96 else 1
    items.sort(key=lambda a: a['ts'], reverse=True)
    items.sort(key=lambda a: a['rank'])
    return items

if __name__ == '__main__':
    arts = news()
    ai = ai_news()
    extra = page_news() + hf_releases()
    have = {a['url'] for a in ai}
    ai = rank_ai(dedupe(ai + [a for a in extra if a['url'] not in have]))[:AI_TOTAL]
    if ai:  # mix the 3 newest AI stories into the main feed
        arts = arts[:2] + ai[:1] + arts[2:6] + ai[1:2] + arts[6:10] + ai[2:3] + arts[10:]
    try: robots = robot_news()
    except Exception as ex:
        print('robots fail', ex, file=sys.stderr); robots = []
    if not robots:
        try: robots = json.load(open(os.path.join(DATA, 'latest.json'))).get('robots', [])
        except Exception: robots = []
    if len(arts) >= 5:
        json.dump({'robots': robots, 'date': datetime.date.today().isoformat(), 'updated': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='minutes'),
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
