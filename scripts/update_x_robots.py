#!/usr/bin/env python3
"""Build data/xposts_robots.json from data/x_raw_robots.json (saved X API v2 get_users_posts responses for robot accounts).
Original posts only (no replies/retweets). @elonmusk, @XPENG_Global and @adcock_brett: robot/humanoid posts only.
Promo, hiring, event-booth and holiday posts dropped. Up to 3 per account, last 60 days; t.co links cleaned."""
import json, os, re, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw = json.load(open(os.path.join(ROOT, 'data', 'x_raw_robots.json'), encoding='utf-8'))
ROBOT = r'\b(robot\w*|humanoid\w*|optimus|iron|figure ?0?\d|helix|neo|atlas|spot|digit|apollo|g1|h1|h2|r1|gr00t|groot|isaac|walker|actuator\w*|hands?|dexter\w*|locomotion|embodied|manipulat\w*|teleop\w*)\b'
STRICT = {'elonmusk', 'xpeng_global', 'adcock_brett'}
BLOCK = r'\b(democrat\w*|republican\w*|trump|biden|election\w*|vote\w*|politic\w*|woke|immigra\w*|lawsuit|stock|shares|lol|lmao)\b'
PROMO = r'\b(giveaway|merch|shop|discount|sale|apply|careers?|hiring|we.?re hiring|job|jobs|internship|sweepstakes|contest|sponsored|ticket\w*|subscribe|webinar|recruit\w*|register|booth|join us|order today|pre-?order|gtc|nvidiagtc|keynote|livestream|rest in peace|rip)\b'
FLUFF = r'(happy|birthday|festival|thank you|congrat\w*|anniversary|holiday|wish\w*|visit us|halloween|mid-autumn|national day)'
CUTOFF = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=60)).strftime('%Y-%m-%dT%H:%M:%S')
def clean(t):
    t = re.sub(r'\s*https://t\.co/\w+', '', t)
    return re.sub(r'\n{3,}', '\n\n', t).strip()
out = []
for acc in raw['accounts']:
    r = acc['posts']; media = {m['media_key']: m for m in r.get('includes', {}).get('media', [])}
    posts = []
    for p in sorted(r.get('data', []), key=lambda p: p['created_at'], reverse=True):
        refs = {x['type'] for x in p.get('referenced_tweets', [])}
        if p['text'].startswith('@') or refs & {'replied_to', 'retweeted'} or p['created_at'] < CUTOFF: continue
        text = clean((p.get('note_tweet') or {}).get('text') or p['text']); low = text.lower()
        if len(re.findall(r"[A-Za-z0-9'’]+", text)) < 3 or re.search(BLOCK, low) or re.search(PROMO, low) or re.search(FLUFF, low): continue
        if acc['username'].lower() in STRICT and not re.search(r'\b(robot\w*|humanoid\w*|optimus|iron|figure ?0?\d|helix|embodied)\b', low): continue
        if acc['username'].lower() == 'elonmusk' and not re.search(r'\b(optimus|robot\w*|humanoid\w*)\b', low): continue
        imgs = [media[k].get('url') or media[k].get('preview_image_url') for k in p.get('attachments', {}).get('media_keys', []) if k in media]
        posts.append({'id': p['id'], 'text': text, 'date': p['created_at'], 'quoted': 'quoted' in refs,
                      'image': next((i for i in imgs if i), None), 'url': f"https://x.com/{acc['username']}/status/{p['id']}"})
        if len(posts) >= 3: break
    if posts: out.append({'handle': acc['username'], 'name': acc['name'], 'avatar': acc['avatar'], 'posts': posts})
json.dump({'updated': raw.get('fetched'), 'accounts': out}, open(os.path.join(ROOT, 'data', 'xposts_robots.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for a in out: print(a['handle'], [p['date'][:10] + ' ' + p['text'][:70].replace('\n', ' ') for p in a['posts']])
