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
