#!/usr/bin/env python3
"""Build data/xfeatured.json from data/x_raw_featured.json (saved X API v2 get_users_posts responses).
@elonmusk: only posts about tech / AI / science (strict keyword allow-list + block-list for politics,
memes, drama, promos, hiring). @SpaceX: original posts only (no replies). Up to 4 each; t.co links cleaned."""
import json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw = json.load(open(os.path.join(ROOT, 'data', 'x_raw_featured.json'), encoding='utf-8'))
TECH = r'\b(ai|grok|xai|model|neural\w*|neuralink|robot\w*|optimus|robotaxi|cybercab|fsd|autonomy|self-driving|tesla|battery|batteries|chip\w*|fab|terafab|compute|gpu\w*|supercomputer|colossus|starship|falcon|raptor|rocket\w*|launch\w*|orbit\w*|mars|moon|lunar|starlink|satellite\w*|spacex|dragon|booster|engine\w*|physics|science|scien\w*|research|energy|solar|software|algorithm|quantum)\b'
BLOCK = r'\b(democrat\w*|republican\w*|trump|biden|harris|election\w*|vote\w*|voting|government|congress|senat\w*|politic\w*|left|right-wing|woke|immigra\w*|border|media|doxx\w*|lawsuit|court|judge|troubling|madness|safety|hire|hiring|join\w*|engineers?|try|stock|shares|price|money|rich|wealth|lol|lmao|haha|rocks|awesome)\b|@bot\b|\bis this good'
PROMO = r'\b(giveaway|merch|shop|store|discount|sale|apply|careers?|hiring|job|jobs|internship|sweepstakes|contest|sponsored|ticket\w*|subscribe|podcast|webinar|recruit\w*)\b'
import datetime
CUTOFF = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).isoformat()
FLUFF = r'(happy|birthday|festival|solar term|thank you|thanks to|congrat\w*|agrees|anniversary|holiday|what a week|wish\w*|come and chat|visit us|booth|world space week|public day|day \d of|merci|joyeux|bonne f[eê]te)'
def clean(t):
    t = re.sub(r'\s*https://t\.co/\w+', '', t)
    return re.sub(r'\n{3,}', '\n\n', t).strip()
out = []
for acc in raw['accounts']:
    r = acc['posts']; media = {m['media_key']: m for m in r.get('includes', {}).get('media', [])}
    posts = []
    for p in r.get('data', []):
        refs = {x['type'] for x in p.get('referenced_tweets', [])}
        if p['text'].startswith('@') or refs & {'replied_to', 'retweeted'}: continue
        text = clean((p.get('note_tweet') or {}).get('text') or p['text'])
        words = re.findall(r"[A-Za-z0-9'’]+", text)
        if acc['username'].lower() == 'elonmusk':
            low = text.lower()
            if len(words) < 2 or not re.search(TECH, low) or re.search(BLOCK, low) or re.search('[\U0001F602\U0001F923\U0001F606\U0001F480]', text): continue
        elif len(words) < 3 or re.search(PROMO, text.lower()) or re.search(FLUFF, text.lower()): continue
        if p['created_at'] < CUTOFF[:19]: continue
        imgs = [media[k].get('url') or media[k].get('preview_image_url') for k in p.get('attachments', {}).get('media_keys', []) if k in media]
        posts.append({'id': p['id'], 'text': text, 'date': p['created_at'], 'quoted': 'quoted' in refs,
                      'image': next((i for i in imgs if i), None), 'url': f"https://x.com/{acc['username']}/status/{p['id']}"})
        if len(posts) >= 4: break
    if posts: out.append({'handle': acc['username'], 'name': acc['name'], 'avatar': acc['avatar'], 'posts': posts})
json.dump({'accounts': out}, open(os.path.join(ROOT, 'data', 'xfeatured.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for a in out: print(a['handle'], [p['text'][:60] for p in a['posts']])
