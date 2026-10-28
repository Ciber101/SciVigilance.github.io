# SciVigilance

**The daily signal from the edge of everything we know.**

A multi-page static site for daily space and science news, built for GitHub Pages. Vanilla HTML/CSS/JS — no build step.

## Pages
- `Digest.html` — homepage: hero, Daily Digest, Daily X / mission social, Shorts, newsletter signup
- `news.html`, `ai.html`, `posts.html`, `voices.html`, `shorts.html`, `archive.html`
- `about.html`, `newsletter.html`, `404.html`

## Data
- `data/latest.json` — digest feed (date, tagline, articles[], ai[])
- `data/xposts.json` / `data/xfeatured.json` — Latest from X / Frontier Voices
- `data/shorts.json` — latest YouTube Shorts
- `data/backgrounds.json` — hourly background pool manifest (local files under `img/backgrounds/`)

## Notes
- All stories keep their original source links and images.
- Deploy: push to `main` on `Ciber101/SciVigilance.github.io`.

## Local preview
Serve the folder with any static server, e.g. `python -m http.server` or `npx serve`, then open `Digest.html` (`index.html` only redirects there).

## Daily SciVigilance site refresh (every 3 hours PT)
Scheduled at **4:07, 10:07, 16:07, and 22:07 America/Los_Angeles**. The hero line shows a live countdown to the next run.

Run these from the repo root (same order the automation uses):

```bash
python3 scripts/update_news.py          # news + AI feed; also calls update_background
python3 scripts/update_background.py    # rebuild/refresh hourly NASA/ESA/Webb/Hubble/Rubin pool
python3 scripts/update_x.py             # Latest from X (from data/x_raw.json)
python3 scripts/update_x_featured.py    # Frontier Voices (from data/x_raw_featured.json)
python3 scripts/update_shorts.py        # YouTube Shorts list
```

### Backgrounds (`scripts/update_background.py`)
- Builds a pool of **~150+** real space photos stored as compressed ~1920px JPGs in `img/backgrounds/`.
- Sources (reuse-with-credit only): **NASA public domain**, **ESA/Webb & ESA/Hubble CC BY 4.0**, **NOIRLab / Vera C. Rubin CC BY 4.0**.
- Optionally folds in today's **NASA APOD** (image + public domain only) as `apod-today`.
- The browser rotates **hourly** (UTC hour since epoch modulo pool size), with crossfade, preload of the next image, dark overlay, and subtle credit. No extra refresh needed for the hourly change.

### Ticker
The top ticker lists news, X posts, and Shorts. Each item links to a stable `#anchor` on the matching page (`news.html`, `posts.html`, `shorts.html`) with smooth scroll + brief highlight.

## Rockets, agencies & tech advancements section rule
RULE (marc, Oct 28 2026): homepage "Rockets, agencies & tech advancements" section (Digest.html #featuredGrid) shows ONLY group "space" accounts (js/main.js filters it). Content must be rockets / space agencies / launch companies + NON-AI tech advancements (biotech, energy, materials, hardware). NO AI, NO robots, NO basic science (astronomy images, physics, biology, climate, research/discovery posts). update_x_featured.py enforces it with space_ok() (NOT_SPACE_AI / NOT_SPACE_ROBOT / NOT_SPACE_SCIENCE, err on excluding); @elonmusk additionally must match SPACE_OR_TECH. Never put AI accounts (e.g. @MistralAI) in group space. AI and robot accounts stay on voices.html (all groups) and in their own homepage sections. Don't loosen these filters.
