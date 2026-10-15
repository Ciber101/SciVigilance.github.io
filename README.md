# SciVigilance

**The daily signal from the edge of everything we know.**

A multi-page static site for daily space and science news, built for GitHub Pages. Vanilla HTML/CSS/JS — no build step.

## Pages
- `index.html` — hero, Daily Digest, Daily X / mission social, mission telemetry (live orbital diagram), newsletter signup
- `archive.html` — past digests, grouped by date
- `articles/*.html` — 5 demo article pages (JWST, Artemis, CERN, Perseverance, space weather)
- `about.html`, `newsletter.html`, `404.html`

## Data
- `data/latest.json` — digest feed (date, tagline, articles[]). Swap this to go live.
- `data/social.json` — Daily X / mission social highlights.

## Notes
- All demo articles are clearly labeled **Sample / Demo** and use real, credited imagery (NASA, ESA, CERN, NOAA, Wikimedia Commons).
- The digest, archive, and social sections are driven by the JSON files; an empty `articles: []` shows a "No digest yet" state.
- Deploy: push to `main` on a `*.github.io` repo (this one is configured as `Ciber101/SciVigilance.github.io`).

## Local preview
Serve the folder with any static server, e.g. `python -m http.server` or `npx serve`, then open `index.html`.

## Daily data (automated)
- `scripts/update_news.py` pulls real frontier-science stories from public RSS feeds (NASA, ESA, Phys.org, ScienceDaily, Quanta, Science News, New Scientist) plus AI model news (Hugging Face, Google DeepMind, OpenAI, Simon Willison, Ars Technica, The Verge, MIT News, MarkTechPost; filtered for releases/benchmarks) into `data/latest.json` — every item keeps its original link and image — and picks the day's public-domain NASA background images into `data/backgrounds.json`.
- `scripts/update_x.py` rebuilds `data/xposts.json` (Latest from X) from the committed `data/x_raw.json` (X reads need auth, so that file is refreshed outside Actions).
- `data/shorts.json` lists the latest YouTube Shorts.
- `.github/workflows/daily-update.yml` runs both scripts daily and commits the data. No secrets needed.
- `scripts/update_x_featured.py` builds `data/xfeatured.json` (front-page "Frontier Voices": @elonmusk tech/AI/science posts only, plus original posts from SpaceX, NASA, ESA, ISRO, CNES, JAXA, Blue Origin, Rocket Lab, ULA, Arianespace, Relativity, Firefly, ispace, LandSpace, CAS Space) from the committed `data/x_raw_featured.json`.
- `scripts/update_shorts.py` refreshes `data/shorts.json` from the channel RSS (with retries), uploads-playlist RSS, or YouTube Data API fallback (Shorts only).
