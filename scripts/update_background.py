#!/usr/bin/env python3
"""Build / refresh the SciVigilance hourly background image pool.

Downloads real space photos (NASA public domain, ESA/Webb/Hubble CC BY 4.0,
NOIRLab/Rubin CC BY 4.0), compresses them to ~1920px-wide JPGs under
img/backgrounds/, and writes data/backgrounds.json (manifest + credits).

The site rotates client-side every UTC hour through this pool (see js/main.js).
On each refresh we also try to fold in today's NASA APOD (image-only, public
domain) as the slot id "apod-today".

Safe to re-run: skips downloads whose local file already exists and looks valid
unless --force is passed. Use --max N to cap new downloads during testing.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from PIL import Image
Image.MAX_IMAGE_PIXELS = 300_000_000  # some ESA/Hubble masters are huge; we resize immediately

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUT_DIR = os.path.join(ROOT, 'img', 'backgrounds')
MANIFEST = os.path.join(DATA, 'backgrounds.json')
UA = {
    'User-Agent': 'SciVigilance-backgrounds/2.0 (+https://ciber101.github.io/SciVigilance.github.io/; space-news site; reuse with credit)'
}
TARGET = 150
MAX_WIDTH = 1920
JPEG_QUALITY = 82
MIN_BYTES = 20_000

# Hand-picked NASA Image Library IDs (real telescope / probe imagery).
NASA_SEED = [
    'PIA04921', 'PIA15985', 'PIA18164', 'PIA23122', 'PIA03606', 'PIA12348', 'PIA22568',
    'PIA17563', 'PIA09579', 'PIA04230', 'PIA14417', 'PIA20061', 'PIA18906', 'PIA21923',
    'PIA01322', 'PIA00400', 'PIA00342', 'PIA01130', 'PIA01492', 'PIA02225', 'PIA02863',
    'PIA03152', 'PIA03519', 'PIA03853', 'PIA04608', 'PIA04866', 'PIA05982', 'PIA06077',
    'PIA07784', 'PIA08329', 'PIA08813', 'PIA11133', 'PIA12110', 'PIA12235', 'PIA13635',
    'PIA13773', 'PIA14884', 'PIA14925', 'PIA15254', 'PIA15624', 'PIA15817', 'PIA16227',
    'PIA16613', 'PIA16884', 'PIA17031', 'PIA17046', 'PIA17550', 'PIA17843', 'PIA18033',
    'PIA18305', 'PIA19048', 'PIA19337', 'PIA19821', 'PIA20016', 'PIA20017', 'PIA20527',
    'PIA21073', 'PIA21425', 'PIA21459', 'PIA21982', 'PIA22031', 'PIA22182', 'PIA22418',
    'PIA22837', 'PIA23122', 'PIA23499', 'PIA23623', 'PIA23868', 'PIA24472', 'PIA24534',
    'hubble-ngc1300', 'hubble-sees-a-horsehead-of-a-different-color',
    'GSFC_20171208_Archive_e001861', 'GSFC_20171208_Archive_e001647',
    'GSFC_20171208_Archive_e000143', 'GSFC_20171208_Archive_e000208',
    'GSFC_20171208_Archive_e001216', 'GSFC_20171208_Archive_e001531',
    'hubble-captures-view-of-mystic-mountain', 'hubble-sharpest-ever-view-of-the-orion-nebula',
    'hubble-views-the-star-that-changed-the-universe', 'stsci-h-p1917b-m-1670x1510',
    'stsci-h-p2016a-m-1599x2000', 'stsci-h-p1936a-m', 'stsci-h-p1821a-m-2291x2000',
    'stsci-h-p1712c-m-1999x2000', 'stsci-h-p1635a-m-1345x1345',
    'jwst-spitzer-carina', 'jwst-smacs0723', 'webb-first-deep-field-smacs-0723',
]

NASA_QUERIES = [
    'hubble nebula', 'hubble galaxy', 'spitzer nebula', 'chandra galaxy cluster',
    'cassini saturn', 'juno jupiter', 'galileo europa', 'voyager neptune',
    'mars curiosity landscape', 'mars perseverance', 'lunar south pole',
    'solar dynamics observatory', 'parker solar probe', 'jwst nebula',
    'jwst galaxy', 'pillars of creation', 'crab nebula', 'orion nebula',
    'andromeda galaxy', 'carina nebula', 'eagle nebula', 'helix nebula',
    'sombrero galaxy', 'whirlpool galaxy', 'antennae galaxies', 'tarantula nebula',
    'ring nebula', ' Lagoon nebula', 'horsehead nebula', 'southern ring nebula',
]

SKIP_TITLE = re.compile(
    r'\b(artist|illustration|concept|infographic|diagram|chart|portrait|headshot|'
    r'meeting|conference|town hall|press conference|engineer|astronaut portrait|'
    r'logo|badge|patch|schematic|screenshot|gui|mock[- ]?up|simulation only|'
    r'people|crowd|ceremony|ribbon)\b',
    re.I,
)


def http_get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_json(url: str, timeout: int = 45):
    return json.loads(http_get(url, timeout=timeout))


def safe_id(s: str) -> str:
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', s.strip())
    return s[:80].strip('_') or 'img'


def prefer_nasa_asset(hrefs: list[str]) -> str | None:
    hrefs = [h.replace('http://', 'https://') for h in hrefs if h]
    for key in ('~large.jpg', '~medium.jpg', '~orig.jpg', '.jpg', '.jpeg', '.png'):
        for h in hrefs:
            if h.lower().endswith(key) or key in h.lower():
                if h.lower().endswith(('.jpg', '.jpeg', '.png')):
                    return h
    for h in hrefs:
        if h.lower().endswith(('.jpg', '.jpeg', '.png')):
            return h
    return None


def collect_nasa_seed(candidates: dict):
    for nid in NASA_SEED:
        if nid in candidates:
            continue
        candidates[nid] = {
            'id': f'nasa_{safe_id(nid)}',
            'nasa_id': nid,
            'title': nid,
            'credit': 'NASA (public domain)',
            'credit_url': f'https://images.nasa.gov/details/{nid}',
            'license': 'NASA public domain',
            'source': 'nasa',
            'url': None,  # resolved later
        }


def collect_nasa_search(candidates: dict, per_query: int = 25):
    for q in NASA_QUERIES:
        url = (
            'https://images-api.nasa.gov/search?'
            + urllib.parse.urlencode({'q': q, 'media_type': 'image', 'page_size': per_query})
        )
        try:
            data = http_json(url)
        except Exception as ex:
            print(f'nasa search fail {q!r}: {ex}', file=sys.stderr)
            continue
        items = (data.get('collection') or {}).get('items') or []
        added = 0
        for it in items:
            meta = (it.get('data') or [{}])[0]
            nid = meta.get('nasa_id')
            title = (meta.get('title') or '').strip()
            if not nid or not title:
                continue
            if SKIP_TITLE.search(title):
                continue
            desc = (meta.get('description') or '')[:400]
            if SKIP_TITLE.search(desc) and 'nebula' not in title.lower() and 'galaxy' not in title.lower():
                continue
            if nid in candidates:
                continue
            candidates[nid] = {
                'id': f'nasa_{safe_id(nid)}',
                'nasa_id': nid,
                'title': title,
                'credit': f'{title} — NASA (public domain)',
                'credit_url': f'https://images.nasa.gov/details/{urllib.parse.quote(nid)}',
                'license': 'NASA public domain',
                'source': 'nasa',
                'url': None,
            }
            added += 1
        print(f'nasa search {q!r}: +{added} (pool {len(candidates)})')
        time.sleep(0.15)


def resolve_nasa_url(entry: dict) -> str | None:
    nid = entry.get('nasa_id')
    if not nid:
        return None
    try:
        meta = http_json('https://images-api.nasa.gov/search?nasa_id=' + urllib.parse.quote(nid))
        items = (meta.get('collection') or {}).get('items') or []
        if items:
            title = ((items[0].get('data') or [{}])[0].get('title') or '').strip()
            if title:
                entry['title'] = title
                entry['credit'] = f'{title} — NASA (public domain)'
        assets = http_json('https://images-api.nasa.gov/asset/' + urllib.parse.quote(nid))
        hrefs = [x.get('href') for x in (assets.get('collection') or {}).get('items') or []]
        return prefer_nasa_asset(hrefs)
    except Exception as ex:
        print(f'nasa resolve {nid}: {ex}', file=sys.stderr)
        return None


def upgrade_esa_cdn(url: str) -> str:
    # Prefer "large" over "screen" / "newsthumb" for backgrounds.
    return re.sub(r'/archives/images/(screen|news|newsfeature|thumb)/', '/archives/images/large/', url)


def parse_rss_images(feed_url: str, source: str, license_name: str, credit_suffix: str, credit_base: str):
    out = []
    try:
        raw = http_get(feed_url)
    except Exception as ex:
        print(f'rss fail {feed_url}: {ex}', file=sys.stderr)
        return out
    try:
        root = ET.fromstring(raw)
    except Exception as ex:
        print(f'rss parse fail {feed_url}: {ex}', file=sys.stderr)
        return out
    for it in root.findall('.//item'):
        title = (it.findtext('title') or '').strip()
        link = (it.findtext('link') or '').strip()
        if not title or SKIP_TITLE.search(title):
            continue
        enc = it.find('enclosure')
        url = enc.get('url') if enc is not None else None
        if not url:
            desc = it.findtext('description') or ''
            m = re.search(r'(https://cdn\.[^"\s>]+\.(?:jpg|jpeg|png))', desc, re.I)
            url = m.group(1) if m else None
        if not url:
            continue
        url = upgrade_esa_cdn(url.replace('http://', 'https://'))
        # Derive a stable id from the page slug or filename.
        slug = urllib.parse.urlparse(link).path.strip('/').split('/')[-1] if link else ''
        if not slug:
            slug = os.path.splitext(os.path.basename(urllib.parse.urlparse(url).path))[0]
        eid = f'{source}_{safe_id(slug)}'
        out.append({
            'id': eid,
            'title': title,
            'credit': f'{title} — {credit_suffix}',
            'credit_url': link or credit_base,
            'license': license_name,
            'source': source,
            'url': url,
        })
    print(f'rss {source}: {len(out)} from {feed_url}')
    return out


def collect_external(candidates: dict):
    feeds = [
        ('https://esawebb.org/images/feed/', 'esawebb', 'ESA/Webb CC BY 4.0',
         'ESA/Webb (CC BY 4.0)', 'https://esawebb.org/images/'),
        ('https://esahubble.org/images/feed/', 'esahubble', 'ESA/Hubble CC BY 4.0',
         'ESA/Hubble (CC BY 4.0)', 'https://esahubble.org/images/'),
        ('https://noirlab.edu/public/images/feed/', 'noirlab', 'NOIRLab/NSF/AURA CC BY 4.0',
         'NOIRLab / NSF / AURA (CC BY 4.0)', 'https://noirlab.edu/public/images/'),
    ]
    for feed_url, source, lic, credit, base in feeds:
        for entry in parse_rss_images(feed_url, source, lic, credit, base):
            key = entry['id']
            if key not in candidates:
                candidates[key] = entry


# Extra famous releases with direct CDN URLs (CC BY / public domain), beyond RSS.
CURATED_DIRECT = [
    {
        'id': 'esawebb_weic2216a',
        'title': "Webb's First Deep Field (SMACS 0723)",
        'url': 'https://cdn.esawebb.org/archives/images/large/weic2216a.jpg',
        'credit_url': 'https://esawebb.org/images/weic2216a/',
        'credit': "Webb's First Deep Field — ESA/Webb (CC BY 4.0)",
        'license': 'ESA/Webb CC BY 4.0',
        'source': 'esawebb',
    },
    {
        'id': 'esawebb_weic2205a',
        'title': 'Southern Ring Nebula (NIRCam)',
        'url': 'https://cdn.esawebb.org/archives/images/large/weic2205a.jpg',
        'credit_url': 'https://esawebb.org/images/weic2205a/',
        'credit': 'Southern Ring Nebula — ESA/Webb (CC BY 4.0)',
        'license': 'ESA/Webb CC BY 4.0',
        'source': 'esawebb',
    },
    {
        'id': 'esawebb_weic2205b',
        'title': 'Southern Ring Nebula (MIRI)',
        'url': 'https://cdn.esawebb.org/archives/images/large/weic2205b.jpg',
        'credit_url': 'https://esawebb.org/images/weic2205b/',
        'credit': 'Southern Ring Nebula MIRI — ESA/Webb (CC BY 4.0)',
        'license': 'ESA/Webb CC BY 4.0',
        'source': 'esawebb',
    },
    {
        'id': 'esawebb_weic2206a',
        'title': "Stephan's Quintet",
        'url': 'https://cdn.esawebb.org/archives/images/large/weic2206a.jpg',
        'credit_url': 'https://esawebb.org/images/weic2206a/',
        'credit': "Stephan's Quintet — ESA/Webb (CC BY 4.0)",
        'license': 'ESA/Webb CC BY 4.0',
        'source': 'esawebb',
    },
    {
        'id': 'esawebb_weic2207a',
        'title': 'Carina Nebula (NIRCam)',
        'url': 'https://cdn.esawebb.org/archives/images/large/weic2207a.jpg',
        'credit_url': 'https://esawebb.org/images/weic2207a/',
        'credit': 'Carina Nebula — ESA/Webb (CC BY 4.0)',
        'license': 'ESA/Webb CC BY 4.0',
        'source': 'esawebb',
    },
    {
        'id': 'esawebb_weic2210b',
        'title': 'Pillars of Creation (NIRCam)',
        'url': 'https://cdn.esawebb.org/archives/images/large/weic2210b.jpg',
        'credit_url': 'https://esawebb.org/images/weic2210b/',
        'credit': 'Pillars of Creation — ESA/Webb (CC BY 4.0)',
        'license': 'ESA/Webb CC BY 4.0',
        'source': 'esawebb',
    },
    {
        'id': 'esawebb_weic2210c',
        'title': 'Pillars of Creation (MIRI)',
        'url': 'https://cdn.esawebb.org/archives/images/large/weic2210c.jpg',
        'credit_url': 'https://esawebb.org/images/weic2210c/',
        'credit': 'Pillars of Creation MIRI — ESA/Webb (CC BY 4.0)',
        'license': 'ESA/Webb CC BY 4.0',
        'source': 'esawebb',
    },
    {
        'id': 'esawebb_weic2311a',
        'title': 'Rho Ophiuchi cloud complex',
        'url': 'https://cdn.esawebb.org/archives/images/large/weic2311a.jpg',
        'credit_url': 'https://esawebb.org/images/weic2311a/',
        'credit': 'Rho Ophiuchi — ESA/Webb (CC BY 4.0)',
        'license': 'ESA/Webb CC BY 4.0',
        'source': 'esawebb',
    },
    {
        'id': 'esawebb_weic2404a',
        'title': 'Crab Nebula (NIRCam)',
        'url': 'https://cdn.esawebb.org/archives/images/large/weic2404a.jpg',
        'credit_url': 'https://esawebb.org/images/weic2404a/',
        'credit': 'Crab Nebula — ESA/Webb (CC BY 4.0)',
        'license': 'ESA/Webb CC BY 4.0',
        'source': 'esawebb',
    },
    {
        'id': 'esawebb_weic2423a',
        'title': 'Cassiopeia A (NIRCam)',
        'url': 'https://cdn.esawebb.org/archives/images/large/weic2423a.jpg',
        'credit_url': 'https://esawebb.org/images/weic2423a/',
        'credit': 'Cassiopeia A — ESA/Webb (CC BY 4.0)',
        'license': 'ESA/Webb CC BY 4.0',
        'source': 'esawebb',
    },
    {
        'id': 'esahubble_heic1502a',
        'title': 'Hubble Ultra Deep Field 2014',
        'url': 'https://cdn.esahubble.org/archives/images/large/heic1502a.jpg',
        'credit_url': 'https://esahubble.org/images/heic1502a/',
        'credit': 'Hubble Ultra Deep Field — ESA/Hubble (CC BY 4.0)',
        'license': 'ESA/Hubble CC BY 4.0',
        'source': 'esahubble',
    },
    {
        'id': 'esahubble_heic0701a',
        'title': 'Hubble Ultra Deep Field',
        'url': 'https://cdn.esahubble.org/archives/images/large/heic0701a.jpg',
        'credit_url': 'https://esahubble.org/images/heic0701a/',
        'credit': 'Hubble Ultra Deep Field — ESA/Hubble (CC BY 4.0)',
        'license': 'ESA/Hubble CC BY 4.0',
        'source': 'esahubble',
    },
    {
        'id': 'esahubble_opo1248a',
        'title': 'Hubble Extreme Deep Field',
        'url': 'https://cdn.esahubble.org/archives/images/large/opo1248a.jpg',
        'credit_url': 'https://esahubble.org/images/opo1248a/',
        'credit': 'Hubble Extreme Deep Field — ESA/Hubble (CC BY 4.0)',
        'license': 'ESA/Hubble CC BY 4.0',
        'source': 'esahubble',
    },
    {
        'id': 'esahubble_heic1501a',
        'title': 'Westerlund 2',
        'url': 'https://cdn.esahubble.org/archives/images/large/heic1501a.jpg',
        'credit_url': 'https://esahubble.org/images/heic1501a/',
        'credit': 'Westerlund 2 — ESA/Hubble (CC BY 4.0)',
        'license': 'ESA/Hubble CC BY 4.0',
        'source': 'esahubble',
    },
    {
        'id': 'esahubble_heic1405a',
        'title': 'Monkey Head Nebula',
        'url': 'https://cdn.esahubble.org/archives/images/large/heic1405a.jpg',
        'credit_url': 'https://esahubble.org/images/heic1405a/',
        'credit': 'Monkey Head Nebula — ESA/Hubble (CC BY 4.0)',
        'license': 'ESA/Hubble CC BY 4.0',
        'source': 'esahubble',
    },
    {
        'id': 'esahubble_heic1301a',
        'title': 'Horsehead Nebula infrared',
        'url': 'https://cdn.esahubble.org/archives/images/large/heic1301a.jpg',
        'credit_url': 'https://esahubble.org/images/heic1301a/',
        'credit': 'Horsehead Nebula — ESA/Hubble (CC BY 4.0)',
        'license': 'ESA/Hubble CC BY 4.0',
        'source': 'esahubble',
    },
    {
        'id': 'esahubble_heic1007a',
        'title': 'Whirlpool Galaxy',
        'url': 'https://cdn.esahubble.org/archives/images/large/heic1007a.jpg',
        'credit_url': 'https://esahubble.org/images/heic1007a/',
        'credit': 'Whirlpool Galaxy — ESA/Hubble (CC BY 4.0)',
        'license': 'ESA/Hubble CC BY 4.0',
        'source': 'esahubble',
    },
    {
        'id': 'esahubble_potw1345a',
        'title': 'Butterfly Nebula',
        'url': 'https://cdn.esahubble.org/archives/images/large/potw1345a.jpg',
        'credit_url': 'https://esahubble.org/images/potw1345a/',
        'credit': 'Butterfly Nebula — ESA/Hubble (CC BY 4.0)',
        'license': 'ESA/Hubble CC BY 4.0',
        'source': 'esahubble',
    },
    # Vera C. Rubin Observatory / NOIRLab first-look and deep fields (CC BY 4.0)
    {
        'id': 'noirlab_noirlab2521a',
        'title': 'Vera C. Rubin Observatory First Look — Virgo Cluster',
        'url': 'https://noirlab.edu/public/media/archives/images/large/noirlab2521a.jpg',
        'credit_url': 'https://noirlab.edu/public/images/noirlab2521a/',
        'credit': 'Rubin First Look Virgo Cluster — NSF–DOE Vera C. Rubin Observatory / NOIRLab (CC BY 4.0)',
        'license': 'NOIRLab/NSF/AURA CC BY 4.0',
        'source': 'noirlab',
    },
    {
        'id': 'noirlab_noirlab2520a',
        'title': 'Rubin Observatory First Look collage',
        'url': 'https://noirlab.edu/public/media/archives/images/large/noirlab2520a.jpg',
        'credit_url': 'https://noirlab.edu/public/images/noirlab2520a/',
        'credit': 'Rubin First Look — NSF–DOE Vera C. Rubin Observatory / NOIRLab (CC BY 4.0)',
        'license': 'NOIRLab/NSF/AURA CC BY 4.0',
        'source': 'noirlab',
    },
    {
        'id': 'noirlab_noirlab2519a',
        'title': 'Trifid and Lagoon Nebulae (Rubin)',
        'url': 'https://noirlab.edu/public/media/archives/images/large/noirlab2519a.jpg',
        'credit_url': 'https://noirlab.edu/public/images/noirlab2519a/',
        'credit': 'Trifid and Lagoon Nebulae — NSF–DOE Vera C. Rubin Observatory / NOIRLab (CC BY 4.0)',
        'license': 'NOIRLab/NSF/AURA CC BY 4.0',
        'source': 'noirlab',
    },
    {
        'id': 'noirlab_noirlab2419a',
        'title': 'Rubin Observatory under the Milky Way',
        'url': 'https://noirlab.edu/public/media/archives/images/large/noirlab2419a.jpg',
        'credit_url': 'https://noirlab.edu/public/images/noirlab2419a/',
        'credit': 'Rubin Observatory — NOIRLab / NSF / AURA (CC BY 4.0)',
        'license': 'NOIRLab/NSF/AURA CC BY 4.0',
        'source': 'noirlab',
    },
]


def collect_direct(candidates: dict):
    for e in CURATED_DIRECT:
        if e['id'] not in candidates:
            candidates[e['id']] = dict(e)


def compress_to_jpg(raw: bytes, dest: str) -> tuple[int, int]:
    im = Image.open(io.BytesIO(raw))
    im = im.convert('RGB')
    w, h = im.size
    if w > MAX_WIDTH:
        nh = int(h * (MAX_WIDTH / w))
        im = im.resize((MAX_WIDTH, nh), Image.Resampling.LANCZOS)
    # Progressive-ish save; optimize for size.
    im.save(dest, format='JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)
    return im.size


def download_one(entry: dict, force: bool = False) -> dict | None:
    eid = entry['id']
    dest = os.path.join(OUT_DIR, eid + '.jpg')
    rel = f'img/backgrounds/{eid}.jpg'
    if (not force) and os.path.isfile(dest) and os.path.getsize(dest) >= MIN_BYTES:
        return {
            'id': eid,
            'file': rel,
            'title': entry.get('title') or eid,
            'credit': entry.get('credit') or '',
            'credit_url': entry.get('credit_url') or '',
            'license': entry.get('license') or '',
            'source': entry.get('source') or '',
        }

    url = entry.get('url')
    if not url and entry.get('nasa_id'):
        url = resolve_nasa_url(entry)
        entry['url'] = url
    if not url:
        print(f'skip {eid}: no url', file=sys.stderr)
        return None

    try:
        raw = http_get(url, timeout=90)
    except Exception as ex:
        # ESA large sometimes 404 → fall back to screen.
        alt = None
        if '/archives/images/large/' in url:
            alt = url.replace('/archives/images/large/', '/archives/images/screen/')
        if alt:
            try:
                raw = http_get(alt, timeout=90)
                url = alt
            except Exception as ex2:
                print(f'dl fail {eid}: {ex} / {ex2}', file=sys.stderr)
                return None
        else:
            print(f'dl fail {eid}: {ex}', file=sys.stderr)
            return None

    if len(raw) < 5000:
        print(f'skip {eid}: tiny payload {len(raw)}', file=sys.stderr)
        return None
    try:
        size = compress_to_jpg(raw, dest)
    except Exception as ex:
        print(f'compress fail {eid}: {ex}', file=sys.stderr)
        if os.path.exists(dest):
            os.remove(dest)
        return None
    if os.path.getsize(dest) < MIN_BYTES:
        print(f'skip {eid}: compressed too small', file=sys.stderr)
        os.remove(dest)
        return None
    print(f'ok {eid} {size[0]}x{size[1]} {os.path.getsize(dest)//1024}KB from {entry.get("source")}')
    return {
        'id': eid,
        'file': rel,
        'title': entry.get('title') or eid,
        'credit': entry.get('credit') or '',
        'credit_url': entry.get('credit_url') or '',
        'license': entry.get('license') or '',
        'source': entry.get('source') or '',
    }


def fetch_apod() -> dict | None:
    key = os.environ.get('NASA_API_KEY', 'DEMO_KEY')
    try:
        a = http_json(f'https://api.nasa.gov/planetary/apod?api_key={urllib.parse.quote(key)}')
    except Exception as ex:
        print(f'APOD skip: {ex}', file=sys.stderr)
        return None
    if a.get('media_type') != 'image':
        print('APOD skip: not an image', file=sys.stderr)
        return None
    # Prefer public-domain (no copyright field). Still allow NASA-hosted with credit if needed.
    img = (a.get('hdurl') or a.get('url') or '').replace('http://', 'https://')
    if not img.lower().endswith(('.jpg', '.jpeg', '.png')):
        print('APOD skip: non-jpg url', file=sys.stderr)
        return None
    copyright_ = (a.get('copyright') or '').strip()
    if copyright_:
        # Skip copyrighted APODs — we only want freely reusable images.
        print(f'APOD skip: copyrighted ({copyright_[:40]})', file=sys.stderr)
        return None
    title = (a.get('title') or 'Astronomy Picture of the Day').strip()
    date = a.get('date') or dt.date.today().isoformat()
    entry = {
        'id': 'apod-today',
        'title': f'APOD {date}: {title}',
        'url': img,
        'credit': f'APOD {date}: {title} — NASA (public domain)',
        'credit_url': 'https://apod.nasa.gov/apod/astropix.html',
        'license': 'NASA public domain',
        'source': 'apod',
    }
    return download_one(entry, force=True)


def load_existing_manifest() -> list:
    if not os.path.isfile(MANIFEST):
        return []
    try:
        data = json.load(open(MANIFEST, encoding='utf-8'))
    except Exception:
        return []
    if isinstance(data, list):
        # Legacy remote-URL list — ignore for local pool.
        return []
    return list(data.get('images') or [])


def write_manifest(images: list, apod: dict | None):
    # Stable order: curated pool sorted by id, with apod-today first when present.
    by_id = {im['id']: im for im in images if im and im.get('id')}
    if apod:
        by_id['apod-today'] = apod
    # Drop stale apod if fetch failed but old file remains — keep file if we already have it.
    ordered = []
    if 'apod-today' in by_id:
        ordered.append(by_id.pop('apod-today'))
    ordered.extend(sorted(by_id.values(), key=lambda x: x['id']))
    payload = {
        'rotation': 'hourly_utc',
        'updated': dt.datetime.now(dt.timezone.utc).isoformat(timespec='minutes'),
        'count': len(ordered),
        'images': ordered,
    }
    os.makedirs(DATA, exist_ok=True)
    json.dump(payload, open(MANIFEST, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'wrote {MANIFEST} count={len(ordered)}')
    return payload


def run(force: bool = False, max_images: int = 0, workers: int = 6, skip_collect: bool = False) -> int:
    """Build/refresh the local background pool. Returns 0 on success."""
    class Args:
        pass
    args = Args()
    args.force = force
    args.max = max_images
    args.workers = workers
    args.skip_collect = skip_collect

    os.makedirs(OUT_DIR, exist_ok=True)
    candidates: dict = {}

    if not args.skip_collect:
        collect_direct(candidates)
        collect_external(candidates)
        collect_nasa_seed(candidates)
        collect_nasa_search(candidates)

    # Prefer entries that already have URLs (ESA/direct) first, then NASA.
    items = list(candidates.values())
    items.sort(key=lambda e: (0 if e.get('url') else 1, e['id']))

    # Cap how many we attempt so we land near TARGET without endless NASA resolves.
    limit = args.max if args.max > 0 else max(TARGET + 40, TARGET)
    items = items[:limit]
    print(f'attempting {len(items)} candidates (target {TARGET})')

    results = []
    # Resolve+download with a modest thread pool. NASA resolve is rate-limited-ish.
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(download_one, e, args.force) for e in items]
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            if r:
                results.append(r)
            if len(results) >= (args.max if args.max > 0 else TARGET + 20):
                break

    # Also keep any local files already on disk that match known pattern (re-run safety).
    existing = {r['id']: r for r in results}
    for name in os.listdir(OUT_DIR):
        if not name.endswith('.jpg'):
            continue
        eid = name[:-4]
        if eid in existing:
            continue
        path = os.path.join(OUT_DIR, name)
        if os.path.getsize(path) < MIN_BYTES:
            continue
        # Try to recover credit from previous manifest.
        prev = {im['id']: im for im in load_existing_manifest()}
        if eid in prev:
            existing[eid] = prev[eid]
        else:
            existing[eid] = {
                'id': eid,
                'file': f'img/backgrounds/{name}',
                'title': eid,
                'credit': 'Space observatory image',
                'credit_url': '',
                'license': '',
                'source': eid.split('_', 1)[0],
            }

    apod = fetch_apod()
    payload = write_manifest(list(existing.values()), apod)
    sources = {}
    for im in payload['images']:
        sources[im.get('source') or '?'] = sources.get(im.get('source') or '?', 0) + 1
    print('sources', sources)
    if payload['count'] < TARGET:
        print(f'WARNING: pool size {payload["count"]} < target {TARGET}', file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--force', action='store_true', help='re-download even if local file exists')
    ap.add_argument('--max', type=int, default=0, help='cap total images in pool (0 = no cap beyond target)')
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--skip-collect', action='store_true', help='only use existing local jpgs + apod')
    ns = ap.parse_args(argv)
    return run(force=ns.force, max_images=ns.max, workers=ns.workers, skip_collect=ns.skip_collect)


if __name__ == '__main__':
    sys.exit(main())
