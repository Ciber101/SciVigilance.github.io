#!/usr/bin/env python3
"""Refresh data/shorts.json from marc's YouTube channel (@ciberaifacts).

Tries, in order:
  1. Channel Atom feed  ?channel_id=UC...  (retries; transient 404s are common)
  2. Uploads playlist feed  ?playlist_id=UU...  (same retries)
  3. YouTube Data API (read-only) via uploader OAuth in /home/box/.secrets/
     or YT_CLIENT_SECRET_JSON / YT_TOKEN_JSON env paths

Only Shorts are kept: RSS entries whose link contains /shorts/, or API items that
are public with duration <= 180s. Merges with previously known Shorts so a feed
outage does not wipe the list.
"""
import json, os, re, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH = 'UCZudcvU912vRNYnb1lCzAdw'
UPLOADS = 'UU' + CH[2:]  # UC... -> UU...
CHANNEL_URL = 'https://www.youtube.com/@ciberaifacts'
OUT = os.path.join(ROOT, 'data', 'shorts.json')
UA = {'User-Agent': 'Mozilla/5.0 (SciVigilance shorts updater; +https://ciber101.github.io/SciVigilance.github.io/)'}
NS = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}
SECRETS_DIR = os.environ.get('YT_SECRETS_DIR', '/home/box/.secrets')
MAX_SHORT_SECONDS = 180
RETRIES = 4
RETRY_SLEEP = 2.0


def load_old():
    if os.path.exists(OUT):
        try:
            return json.load(open(OUT, encoding='utf-8'))
        except Exception:
            pass
    return {'shorts': []}


def fetch_bytes(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_with_retries(url, label):
    last = None
    for i in range(RETRIES):
        try:
            data = fetch_bytes(url)
            print(f'{label}: ok ({len(data)} bytes) attempt {i + 1}')
            return data
        except Exception as ex:
            last = ex
            print(f'{label}: fail attempt {i + 1}/{RETRIES}: {ex}')
            if i + 1 < RETRIES:
                time.sleep(RETRY_SLEEP * (i + 1))
    print(f'{label}: gave up ({last})')
    return None


def parse_atom_shorts(xml_bytes):
    shorts = []
    root = ET.fromstring(xml_bytes)
    for e in root.findall('a:entry', NS):
        link_el = e.find('a:link', NS)
        link = link_el.get('href', '') if link_el is not None else ''
        # Channel/playlist feeds mark Shorts with /shorts/ in the alternate link.
        # Also accept watch URLs when media:group is absent — filter by title tag later only for API.
        if '/shorts/' not in link:
            continue
        vid = e.find('yt:videoId', NS)
        title = e.find('a:title', NS)
        pub = e.find('a:published', NS)
        if vid is None or not vid.text:
            continue
        shorts.append({
            'id': vid.text,
            'title': (title.text or '').strip() if title is not None else '',
            'date': (pub.text or '').strip() if pub is not None else '',
        })
    return shorts


def parse_iso8601_duration(s):
    m = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', s or '')
    if not m:
        return None
    h, mi, sec = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + sec


def oauth_token():
    client_path = os.environ.get('YT_CLIENT_SECRET_JSON', os.path.join(SECRETS_DIR, 'yt_client_secret.json'))
    token_path = os.environ.get('YT_TOKEN_JSON', os.path.join(SECRETS_DIR, 'yt_token.json'))
    if not (os.path.isfile(client_path) and os.path.isfile(token_path)):
        print(f'api: no credentials at {client_path} / {token_path}')
        return None
    c = json.load(open(client_path, encoding='utf-8'))['installed']
    t = json.load(open(token_path, encoding='utf-8'))
    body = urllib.parse.urlencode({
        'refresh_token': t['refresh_token'],
        'client_id': c['client_id'],
        'client_secret': c['client_secret'],
        'grant_type': 'refresh_token',
    }).encode()
    tok = json.load(urllib.request.urlopen(c['token_uri'], body))['access_token']
    return tok


def api_get(tok, path_qs):
    req = urllib.request.Request(
        'https://www.googleapis.com/youtube/v3/' + path_qs,
        headers={'Authorization': 'Bearer ' + tok, **UA},
    )
    return json.load(urllib.request.urlopen(req, timeout=30))


def is_youtube_short(video_id):
    """True if youtube.com/shorts/<id> stays on /shorts/ (non-Shorts redirect to /watch).
    Returns None when the check itself fails (rate limit / network) so callers can fall back."""
    url = f'https://www.youtube.com/shorts/{video_id}'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            return '/shorts/' in (r.geturl() or '')
    except Exception as ex:
        print(f'api: shorts-check fail {video_id}: {ex}')
        return None


def fetch_via_api():
    tok = oauth_token()
    if not tok:
        return None
    print('api: token ok')
    # Confirm channel + uploads playlist
    ch = api_get(tok, f'channels?part=contentDetails,snippet&id={CH}')
    items = ch.get('items') or []
    if not items:
        print('api: channel not found')
        return None
    custom = (items[0].get('snippet') or {}).get('customUrl', '')
    uploads = items[0]['contentDetails']['relatedPlaylists']['uploads']
    print(f'api: channel {CH} customUrl={custom} uploads={uploads}')
    video_ids = []
    page = None
    while len(video_ids) < 50:
        qs = f'playlistItems?part=contentDetails&playlistId={uploads}&maxResults=50'
        if page:
            qs += '&pageToken=' + urllib.parse.quote(page)
        pl = api_get(tok, qs)
        for it in pl.get('items') or []:
            vid = (it.get('contentDetails') or {}).get('videoId')
            if vid:
                video_ids.append(vid)
        page = pl.get('nextPageToken')
        if not page:
            break
    if not video_ids:
        print('api: no uploads')
        return []
    candidates = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        meta = api_get(tok, 'videos?part=snippet,contentDetails,status&id=' + ','.join(batch))
        for v in meta.get('items') or []:
            status = (v.get('status') or {}).get('privacyStatus')
            if status != 'public':
                continue
            dur = parse_iso8601_duration((v.get('contentDetails') or {}).get('duration'))
            if dur is None or dur > MAX_SHORT_SECONDS or dur <= 0:
                continue
            sn = v.get('snippet') or {}
            candidates.append({
                'id': v['id'],
                'title': (sn.get('title') or '').strip(),
                'date': (sn.get('publishedAt') or '').strip(),
            })
    shorts = []
    for c in candidates:
        title_l = c['title'].lower()
        if '#shorts' in title_l or '#short' in title_l:
            shorts.append(c)
            continue
        check = is_youtube_short(c['id'])
        if check is True:
            shorts.append(c)
        elif check is None:
            # Rate limit / network: do not guess — title #shorts already kept above
            print(f'api: shorts-check inconclusive, skip {c["id"]} {c["title"][:50]}')
        else:
            print(f'api: skip non-Short {c["id"]} {c["title"][:50]}')
    print(f'api: {len(shorts)} public Shorts from {len(video_ids)} uploads ({len(candidates)} short-duration candidates)')
    return shorts


def merge(primary, old_list):
    known = {s['id'] for s in primary}
    out = list(primary)
    for s in old_list:
        if s.get('id') and s['id'] not in known:
            out.append(s)
            known.add(s['id'])
    out.sort(key=lambda s: s.get('date') or '', reverse=True)
    return out


def main():
    old = load_old()
    shorts = None
    source = None

    xml = fetch_with_retries(
        f'https://www.youtube.com/feeds/videos.xml?channel_id={CH}', 'channel_rss')
    if xml:
        shorts = parse_atom_shorts(xml)
        source = 'channel_rss'
        print(f'channel_rss: {len(shorts)} Shorts in feed')

    if not shorts:
        xml = fetch_with_retries(
            f'https://www.youtube.com/feeds/videos.xml?playlist_id={UPLOADS}', 'playlist_rss')
        if xml:
            shorts = parse_atom_shorts(xml)
            source = 'playlist_rss'
            print(f'playlist_rss: {len(shorts)} Shorts in feed')

    if not shorts:
        try:
            api_shorts = fetch_via_api()
        except Exception as ex:
            print('api: fail', ex)
            api_shorts = None
        if api_shorts is not None:
            shorts = api_shorts
            source = 'youtube_api'

    if shorts is None:
        print('all sources failed; keeping previous list')
        shorts = old.get('shorts', [])
        source = 'previous'
    elif source == 'youtube_api':
        # Full uploads scan is authoritative; do not re-introduce non-Shorts
        # that may have been written by an earlier buggy run.
        shorts = sorted(shorts, key=lambda s: s.get('date') or '', reverse=True)
    else:
        # RSS only covers the newest ~15 uploads; keep older known Shorts.
        shorts = merge(shorts, old.get('shorts', []))

    payload = {'channel': CHANNEL_URL, 'shorts': shorts}
    json.dump(payload, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('wrote', OUT, 'source=', source, 'shorts=', len(shorts))
    for s in shorts[:8]:
        print(' ', s['id'], s.get('date', '')[:10], s.get('title', '')[:70])


if __name__ == '__main__':
    main()
