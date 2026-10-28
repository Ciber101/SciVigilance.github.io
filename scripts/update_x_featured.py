#!/usr/bin/env python3
"""Build data/xfeatured.json (groups: ai, robots, space; order AI frontier labs -> other AI -> robots -> space) from data/x_raw_featured.json (saved X API v2 get_users_posts responses).
@elonmusk: only posts about tech / AI / science (strict keyword allow-list + block-list for politics,
memes, drama, promos, hiring). @SpaceX: original posts only (no replies). Up to 4 each; t.co links cleaned."""
import json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw = json.load(open(os.path.join(ROOT, 'data', 'x_raw_featured.json'), encoding='utf-8'))
TECH = r'\b(ai|grok|xai|model|neural\w*|neuralink|robot\w*|optimus|robotaxi|cybercab|fsd|autonomy|self-driving|tesla|battery|batteries|chip\w*|fab|terafab|compute|gpu\w*|supercomputer|colossus|starship|falcon|raptor|rocket\w*|launch\w*|orbit\w*|mars|moon|lunar|starlink|satellite\w*|spacex|dragon|booster|engine\w*|physics|science|scien\w*|research|energy|solar|software|algorithm|quantum)\b'
BLOCK = r'\b(democrat\w*|republican\w*|trump|biden|harris|election\w*|vote\w*|voting|government|congress|senat\w*|politic\w*|left|right-wing|woke|immigra\w*|border|media|doxx\w*|lawsuit|court|judge|troubling|madness|safety|hire|hiring|join\w*|engineers?|try|stock|shares|price|money|rich|wealth|lol|lmao|haha|rocks|awesome)\b|@bot\b|\bis this good'
PROMO = r'\b(giveaway|merch|shop|store|discount|sale|apply|careers?|hiring|job|jobs|internship|sweepstakes|contest|sponsored|ticket\w*|subscribe|podcast|webinar|recruit\w*)\b'
import datetime, ast
# shared topic filters from update_news.py (AI_GOOD, FRONTIER_KW, LOCAL_KW, HUMANOID_KW, ROBOT_OK)
_src = open(os.path.join(ROOT, 'scripts', 'update_news.py'), encoding='utf-8').read()
_kw = {n.targets[0].id: ast.literal_eval(n.value) for n in ast.parse(_src).body
       if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ('AI_GOOD', 'FRONTIER_KW', 'LOCAL_KW', 'HUMANOID_KW', 'ROBOT_OK')}
AI_TOPIC = '|'.join('(?:%s)' % _kw[k] for k in ('AI_GOOD', 'FRONTIER_KW', 'LOCAL_KW') if k in _kw) + r'|\b(ai|agi|agents?|reasoning|training|inference|compute|gpu\w*|research|paper|benchmark\w*)\b'
ROBOT_TOPIC = '|'.join('(?:%s)' % _kw[k] for k in ('HUMANOID_KW', 'ROBOT_OK') if k in _kw) + r'|\b(robot\w*|humanoid\w*|optimus|helix|embodied)\b'
# people / mixed-topic accounts: post kept only if it matches the group topic
TOPIC_ONLY = {'sama', 'demishassabis', 'darioamodei', 'karpathy', 'ylecun', 'nvidia', 'adcock_brett', 'xpeng_global', 'nvidiarobotics'}
PROMO_AI = r'\b(livestream|live stream|tune in|join us|register|keynote|gtc|sign up|waitlist|% off|free trial|promo code|use code|limited time|students?|applications?|fellowships?|nasdaq|ipo|sec|investors?|earnings|chief executive|ceo)\b'
# robots: reuse the robot page fetch (no extra reads)
_rob = json.load(open(os.path.join(ROOT, 'data', 'x_raw_robots.json'), encoding='utf-8'))
_have = {a['username'].lower() for a in raw['accounts']}
for _a in _rob['accounts']:
    if _a['username'].lower() not in _have: raw['accounts'].append(dict(_a, group='robots'))
# Homepage "Rockets, agencies & tech advancements" section = group 'space' only (marc, Oct 28 2026):
# rockets / space agencies / launch companies + NON-AI tech advancements (biotech, energy, materials, hardware).
# NO AI, NO robots, NO basic science. Err on the side of excluding.
NOT_SPACE_AI = r'\b(ai|a\.i\.|agi|artificial intelligence|machine learning|ml|llms?|gpt\w*|grok\w*|xai|chatbot\w*|neural\w*|model|models|agents?|agentic|api|apis|inference|training|compute|gpus?|datacenters?|data centers?|colossus|supercomputer\w*|openai|anthropic|claude|gemini|mistral|deepseek|qwen|llama|copilot|chatgpt|imagine|autonomy|autonomous|self-driving|fsd|robotaxi|cybercab|algorithm\w*|intelligen\w*)\b'
NOT_SPACE_ROBOT = r'\b(robot\w*|humanoid\w*|optimus|android|droid\w*|embodied|rover\w*|helix|figure 0?\d)\b'
NOT_SPACE_SCIENCE = r'\b(scien\w*|galax\w*|nebula\w*|black holes?|stars?|stellar|cosmic|cosmos|universe|light-years?|exoplanet\w*|supernova\w*|telescope\w*|webb|hubble|asteroids?|comets?|meteor\w*|eclipse\w*|full moon|hunter.s moon|night sky|solar (?:eruption|flare|wind|storm)\w*|sun.s|relativity|einstein|physics|quantum|particle\w*|fossil\w*|dinosaur\w*|species|evolution\w*|climate|weather|ocean\w*|geolog\w*|biolog\w*|chemistry|astronom\w*|astrophysic\w*|planetary science|research\w*|study|studies|discover\w*|observ\w*|météo|relativité|scientifique\w*)\b'
SPACE_OR_TECH = r'\b(starship|falcon|raptor|rocket\w*|launch\w*|orbit\w*|mars|moon|lunar|starlink|satellite\w*|spacex|dragon|booster|engine\w*|spacecraft|space|nasa|esa|artemis|battery|batteries|chip\w*|fab|terafab|semiconductor\w*|energy|solar panel\w*|solar power|fusion|reactor|nuclear|materials?|biotech\w*|neuralink|tunnel\w*|boring|hyperloop|ev|evs|tesla|cybertruck|megapack|powerwall)\b'
def space_ok(low):
    return not (re.search(NOT_SPACE_AI, low) or re.search(NOT_SPACE_ROBOT, low) or re.search(NOT_SPACE_SCIENCE, low))
_rank = {'ai': 0, 'robots': 1, 'space': 2}
raw['accounts'].sort(key=lambda a: _rank.get(a.get('group', 'space'), 2))  # stable: keeps list order inside a group
CUTOFF = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).isoformat()
FLUFF = r'(happy|birthday|festival|solar term|thank you|thanks to|congrat\w*|agrees|anniversary|holiday|what a week|wish\w*|come and chat|visit us|booth|world space week|public day|day \d of|merci|joyeux|bonne f[eê]te)'
def clean(t):
    t = re.sub(r'\s*https://t\.co/\w+', '', t)
    return re.sub(r'\n{3,}', '\n\n', t).strip()
def best_video(m):
    v = [x for x in (m or {}).get('variants', []) if x.get('content_type') == 'video/mp4' and x.get('url')]
    return max(v, key=lambda x: x.get('bit_rate') or 0)['url'] if v and m.get('type') in ('video', 'animated_gif') else None
out = []
for acc in raw['accounts']:
    r = acc['posts']; media = {m['media_key']: m for m in r.get('includes', {}).get('media', [])}
    posts = []
    for p in sorted(r.get('data', []), key=lambda p: p['created_at'], reverse=True):
        refs = {x['type'] for x in p.get('referenced_tweets', [])}
        if p['text'].startswith('@') or refs & {'replied_to', 'retweeted'}: continue
        text = clean((p.get('note_tweet') or {}).get('text') or p['text'])
        words = re.findall(r"[A-Za-z0-9'’]+", text)
        if acc['username'].lower() == 'elonmusk':
            low = text.lower()
            if len(words) < 2 or not re.search(TECH, low) or re.search(BLOCK, low) or re.search('[\U0001F602\U0001F923\U0001F606\U0001F480]', text): continue
        elif acc.get('group') in ('ai', 'robots'):
            low = text.lower()
            topic = AI_TOPIC if acc['group'] == 'ai' else ROBOT_TOPIC
            if len(words) < 3 or re.search(PROMO, low) or re.search(PROMO_AI, low) or re.search(FLUFF, low) or re.search(BLOCK.replace('|engineers?|try', ''), low): continue
            if acc['username'].lower() in TOPIC_ONLY and not re.search(topic, low, re.I): continue
            if acc['username'].lower() in ('xpeng_global', 'adcock_brett') and not re.search(r'\b(robot\w*|humanoid\w*|iron|figure ?0?\d|f\.0\d|helix|embodied)\b', low): continue
        elif len(words) < 3 or re.search(PROMO, text.lower()) or re.search(FLUFF, text.lower()): continue
        if acc.get('group', 'space') == 'space':
            low = text.lower()
            if not space_ok(low): continue
            if acc['username'].lower() == 'elonmusk' and not re.search(SPACE_OR_TECH, low): continue
        if p['created_at'] < CUTOFF[:19]: continue
        imgs = [media[k].get('url') or media[k].get('preview_image_url') for k in p.get('attachments', {}).get('media_keys', []) if k in media]
        vids = [best_video(media[k]) for k in p.get('attachments', {}).get('media_keys', []) if k in media]
        posts.append({'id': p['id'], 'text': text, 'date': p['created_at'], 'quoted': 'quoted' in refs,
                      'image': next((i for i in imgs if i), None), 'video': next((v for v in vids if v), None), 'url': f"https://x.com/{acc['username']}/status/{p['id']}"})
        if len(posts) >= 4: break
    if posts: out.append({'handle': acc['username'], 'name': acc['name'], 'group': acc.get('group', 'space'), 'avatar': acc['avatar'], 'posts': posts})
json.dump({'accounts': out}, open(os.path.join(ROOT, 'data', 'xfeatured.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for a in out: print(a['handle'], [p['text'][:60] for p in a['posts']])
