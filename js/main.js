/* ============================================================
   SciVigilance — main.js
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  initNavToggle();
  initStarfield();
  Promise.all([
    loadDigest(),
    loadX(),
    loadFeatured(),
    loadShorts(),
  ]).then(() => {
    // Cards exist — honor deep links from the ticker / shared URLs.
    jumpToHash();
    setTimeout(jumpToHash, 400);
  });
  loadBackground();
  initRefreshCountdown();
  if (document.getElementById('archiveList')) loadArchive();
  if (document.getElementById('allNewsGrid') || document.getElementById('allAiGrid')) loadFullList();
  window.addEventListener('resize', clampRows);
  window.addEventListener('hashchange', jumpToHash);
});

/* ---------- Nav toggle ---------- */
function initNavToggle() {
  const toggle = document.getElementById('navToggle');
  const links = document.getElementById('navLinks');
  if (!toggle || !links) return;
  toggle.addEventListener('click', () => {
    const open = links.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open);
  });
}

/* ---------- Star field (hero) ---------- */
function initStarfield() {
  const canvas = document.getElementById('starfield');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let stars = [];
  let w, h, dpr;

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const rect = canvas.parentElement.getBoundingClientRect();
    w = rect.width;
    h = rect.height;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    seed();
  }

  function seed() {
    const count = Math.min(Math.floor(w * h / 3200), 460);
    stars = Array.from({ length: count }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 1.4 + 0.3,
      a: Math.random() * 0.7 + 0.25,
      tw: Math.random() * 0.02 + 0.005,
      ph: Math.random() * Math.PI * 2,
      hue: Math.random() < 0.5 ? 185 : 0,
    }));
  }

  let t = 0;
  function draw() {
    ctx.clearRect(0, 0, w, h);
    t += 1;
    for (const s of stars) {
      const alpha = s.a * (0.6 + 0.4 * Math.sin(t * s.tw + s.ph));
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      if (s.hue) {
        ctx.fillStyle = `hsla(${s.hue}, 70%, 72%, ${alpha})`;
      } else {
        ctx.fillStyle = `rgba(220,230,255,${alpha})`;
      }
      ctx.fill();
    }
    requestAnimationFrame(draw);
  }

  resize();
  window.addEventListener('resize', resize);
  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    requestAnimationFrame(draw);
  } else {
    draw(); // single static frame
  }
}


/* ---------- Digest ---------- */
async function loadDigest() {
  const grid = document.getElementById('digestGrid');
  const empty = document.getElementById('digestEmpty');
  if (!grid) return;
  let data;
  try {
    const res = await fetch('data/latest.json');
    data = await res.json();
  } catch (e) {
    showEmpty(empty);
    return;
  }

  const tagline = document.getElementById('digestTagline');
  if (tagline && data.tagline) tagline.textContent = data.tagline;

  const articles = (data.articles || []).slice().sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  if (!articles.length) { showEmpty(empty); return; }

  grid.querySelectorAll('.card').forEach(c => c.remove());
  currentArticles = articles;
  articles.forEach(a => grid.appendChild(makeCard(a)));
  buildTicker(articles);
  const ai = document.getElementById('aiGrid');
  if (ai) {
    const list = data.ai || [];
    if (!list.length) ai.closest('section').hidden = true;
    list.forEach(a => ai.appendChild(makeCard(a)));
    currentArticles = currentArticles.concat(list);
  }
  clampRows();
}

function showEmpty(el) {
  if (el) el.hidden = false;
}

function makeCard(a) {
  const card = document.createElement('article');
  card.className = 'card';
  const aid = itemAnchorId('news', a.id || a.url || a.title);
  card.id = aid;
  card.setAttribute('data-anchor', aid);
  const tag = (a.tags && a.tags[0]) || '';
  const url = safeUrl(a.url);
  card.innerHTML = `
    <a href="${url}" class="thumb" tabindex="-1" aria-hidden="true" target="_blank" rel="noopener">
      <img src="${safeUrl(a.image)}" alt="" loading="lazy" referrerpolicy="no-referrer">
      ${tag ? `<span class="badge-tag${tag === 'AI' ? ' ai' : ''}">${escapeHtml(tag)}</span>` : ''}
      <span class="img-credit">Image via ${escapeHtml(a.source || 'source')}</span>
    </a>
    <div class="body">
      <div class="meta"><span class="time">${escapeHtml(a.date || '')}</span><span>·</span><span>${escapeHtml(a.source || '')}</span></div>
      <h3><a href="${url}" target="_blank" rel="noopener">${escapeHtml(a.title)}</a></h3>
      <p class="summary">${escapeHtml(a.summary || '')}</p>
      <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:4px;">
        <a href="${url}" class="read" target="_blank" rel="noopener">Read at ${escapeHtml(a.source || 'source')} <span aria-hidden="true">↗</span></a>
        <button class="btn btn-ghost share-btn" style="padding:6px 12px;font-size:0.78rem;" aria-label="Share on X">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg> Share
        </button>
      </div>
    </div>`;
  return card;
}

function shareOnX(a) {
  const u = `https://twitter.com/intent/tweet?text=${encodeURIComponent(a.title + ' via @SciVigil')}&url=${encodeURIComponent(a.url)}`;
  window.open(u, '_blank', 'noopener,width=600,height=520');
}
document.addEventListener('click', e => {
  const b = e.target.closest('.share-btn');
  if (!b) return;
  e.preventDefault();
  const link = b.closest('.card').querySelector('h3 a');
  const art = currentArticles.find(x => x.url === link.href);
  if (art) shareOnX(art);
});

function safeUrl(u) {
  u = String(u || '');
  return /^https?:\/\//i.test(u) || /^[\w./-]+$/.test(u) ? escapeHtml(u) : '#';
}

/** Stable DOM id for in-page anchors (news / X / Shorts). */
function itemAnchorId(kind, key) {
  const raw = String(key || '').toLowerCase();
  const slug = raw.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 72);
  return `${kind}-${slug || 'item'}`;
}

function tickerHref(kind, key, page) {
  const id = itemAnchorId(kind, key);
  // On the page that owns the full list, use a hash; elsewhere link to that page.
  const here = (location.pathname.split('/').pop() || 'index.html').toLowerCase();
  const target = (page || '').toLowerCase();
  if (here === target || (here === 'index.html' && false)) return `#${id}`;
  // Index also renders cards — prefer in-page jump when the element exists after load.
  // buildTicker runs before all grids finish, so use the dedicated list page for reliability
  // except when we are already on that page.
  if (here === 'index.html') return `${page}#${id}`;
  return here === target ? `#${id}` : `${page}#${id}`;
}

function highlightAnchor(el) {
  if (!el) return;
  el.classList.remove('anchor-flash');
  void el.offsetWidth;
  el.classList.add('anchor-flash');
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  // Unhide if clampRows hid it
  el.hidden = false;
}

function jumpToHash() {
  const id = (location.hash || '').replace(/^#/, '');
  if (!id) return;
  const el = document.getElementById(id);
  if (el) highlightAnchor(el);
}

let currentArticles = [];
let tickerExtras = { posts: [], shorts: [] };

function buildTicker(articles) {
  currentArticles = articles;
  const track = document.getElementById('tickerTrack');
  if (!track) return;
  const parts = [];
  (articles || []).forEach(a => {
    const href = tickerHref('news', a.id || a.url || a.title, 'news.html');
    const tag = (a.tags && a.tags[0]) || 'SIGNAL';
    parts.push(`<a class="ticker-item" href="${escapeHtml(href)}"><b>${escapeHtml(tag)}</b> ${escapeHtml(a.title)}</a>`);
  });
  (tickerExtras.posts || []).slice(0, 12).forEach(p => {
    const href = tickerHref('x', p.id || p.url, 'posts.html');
    const label = (p.text || '').replace(/\s+/g, ' ').trim().slice(0, 90);
    if (!label) return;
    parts.push(`<a class="ticker-item" href="${escapeHtml(href)}"><b>X</b> ${escapeHtml(label)}${label.length >= 90 ? '…' : ''}</a>`);
  });
  (tickerExtras.shorts || []).slice(0, 8).forEach(s => {
    const href = tickerHref('short', s.id, 'shorts.html');
    parts.push(`<a class="ticker-item" href="${escapeHtml(href)}"><b>SHORT</b> ${escapeHtml(s.title || s.id)}</a>`);
  });
  if (!parts.length) return;
  const items = parts.join('');
  track.innerHTML = items + items; // duplicate for seamless loop
  // constant ~45px/s no matter how long the headline list is
  const setSpeed = () => { const half = track.scrollWidth / 2; if (half > 0) track.style.animationDuration = Math.round(half / 45) + 's'; };
  requestAnimationFrame(setSpeed);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(setSpeed);
}

function rebuildTickerIfReady() {
  if (currentArticles && currentArticles.length) buildTicker(currentArticles);
}

/* ---------- Latest from X (@SciVigil) ---------- */
async function loadX() {
  const grid = document.getElementById('xGrid') || document.getElementById('allPostsGrid');
  if (!grid) return;
  const empty = document.getElementById('xEmpty');
  let data;
  try { data = await (await fetch('data/xposts.json')).json(); } catch (e) { showEmpty(empty); return; }
  const posts = data.posts || [];
  if (!posts.length) { showEmpty(empty); return; }
  tickerExtras.posts = posts;
  rebuildTickerIfReady();
  posts.forEach(p => {
    const el = document.createElement('article');
    el.className = 'social-card x-card';
    const xid = itemAnchorId('x', p.id || p.url);
    el.id = xid;
    el.setAttribute('data-anchor', xid);
    const text = escapeHtml(p.text || '').replace(/(^|\s)(#\w+)/g, '$1<span class="ht">$2</span>');
    const when = p.date ? new Date(p.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '';
    el.innerHTML = `
      <div class="x-head"><img class="x-av" src="img/scivigil-avatar.jpg" alt="@SciVigil profile picture" width="36" height="36"><span class="x-name"><b>${escapeHtml(data.name || 'SciVigil')}</b><span>@${escapeHtml(data.handle || 'SciVigil')}</span></span></div>
      <p class="text">${text}${p.truncated ? '…' : ''}</p>
      ${p.image ? `<img src="${safeUrl(p.image)}" alt="" loading="lazy">` : ''}
      ${p.link ? `<a class="x-link" href="${safeUrl(p.link)}" target="_blank" rel="noopener">🔗 Source link</a>` : ''}
      <div class="foot">
        <span class="label">${escapeHtml(when)}</span>
        <a class="ext" href="${safeUrl(p.url)}" target="_blank" rel="noopener">${p.truncated ? 'Read on X' : 'View on X'} ↗</a>
      </div>`;
    grid.appendChild(el);
  });
  const count = document.getElementById('pageCount');
  if (count && grid.id === 'allPostsGrid') count.textContent = `${posts.length} posts`;
  clampRows();
}

/* ---------- Featured accounts (@elonmusk tech/AI/science only, @SpaceX originals) ---------- */
function featuredCard({ acc, p }) {
  const when = p.date ? new Date(p.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '';
  const text = escapeHtml(p.text || '').replace(/(^|\s)([#@]\w+)/g, '$1<span class="ht">$2</span>');
  const fid = itemAnchorId('voice', (p.id || p.url || '') + '-' + acc.handle);
  return `<article class="social-card x-card" id="${fid}" data-anchor="${fid}" data-acc="${escapeHtml(acc.handle)}">
    <div class="x-head"><img class="x-av" src="${safeUrl(acc.avatar)}" alt="@${escapeHtml(acc.handle)} profile picture" width="36" height="36"><span class="x-name"><b>${escapeHtml(acc.name)}</b><span>@${escapeHtml(acc.handle)}</span></span></div>
    <p class="text">${text}</p>
    ${p.image ? `<img src="${safeUrl(p.image)}" alt="" loading="lazy">` : ''}
    ${p.quoted ? '<span class="x-link">Quoted a post · see it on X</span>' : ''}
    <div class="foot"><span class="label">${escapeHtml(when)}</span><a class="ext" href="${safeUrl(p.url)}" target="_blank" rel="noopener">View on X ↗</a></div>
  </article>`;
}

async function loadFeatured() {
  const grid = document.getElementById('featuredGrid') || document.getElementById('allVoicesGrid');
  if (!grid) return;
  let d;
  try { d = await (await fetch('data/xfeatured.json')).json(); } catch (e) { return; }
  const cards = [];
  (d.accounts || []).forEach(acc => (acc.posts || []).forEach(p => cards.push({ acc, p })));
  cards.sort((a, b) => (b.p.date || '').localeCompare(a.p.date || ''));
  if (grid.id === 'featuredGrid') {
    if (!cards.length) return;
    grid.innerHTML = cards.map(featuredCard).join('');
    grid.closest('section').hidden = false;
    clampRows();
    return;
  }
  const count = document.getElementById('pageCount');
  if (count) count.textContent = `${cards.length} posts from ${(d.accounts || []).length} accounts`;
  if (!cards.length) { grid.innerHTML = '<div class="empty-state"><div class="icon">📡</div><h3>No recent posts.</h3><p>Check back soon.</p></div>'; return; }
  grid.innerHTML = cards.map(featuredCard).join('');
  const chips = document.getElementById('chips');
  if (chips) {
    chips.hidden = false;
    chips.innerHTML = '<button type="button" class="chip on" data-acc="">All</button>' + (d.accounts || []).map(a => `<button type="button" class="chip" data-acc="${escapeHtml(a.handle)}">${escapeHtml(a.name)}</button>`).join('');
    chips.addEventListener('click', e => {
      const b = e.target.closest('.chip'); if (!b) return;
      chips.querySelectorAll('.chip').forEach(c => c.classList.toggle('on', c === b));
      grid.querySelectorAll('.x-card').forEach(c => { c.hidden = !!b.dataset.acc && c.dataset.acc !== b.dataset.acc; });
    });
  }
}

/* ---------- Latest YouTube Shorts ---------- */
async function loadShorts() {
  const grid = document.getElementById('shortsGrid') || document.getElementById('allShortsGrid');
  if (!grid) return;
  try {
    const d = await (await fetch('data/shorts.json')).json();
    const list = d.shorts || [];
    if (!list.length) throw new Error('none');
    tickerExtras.shorts = list;
    rebuildTickerIfReady();
    grid.innerHTML = list.map(v => {
      const sid = itemAnchorId('short', v.id);
      return `
      <div class="short-card" id="${sid}" data-anchor="${sid}"><div class="frame"><iframe loading="lazy" src="https://www.youtube-nocookie.com/embed/${encodeURIComponent(v.id)}" title="${escapeHtml(v.title)}" allow="accelerometer; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>
      <p><a href="https://www.youtube.com/shorts/${encodeURIComponent(v.id)}" target="_blank" rel="noopener">${escapeHtml(v.title)}</a></p></div>`;
    }).join('');
    const count = document.getElementById('pageCount');
    if (count) count.textContent = `${list.length} Short${list.length === 1 ? '' : 's'}`;
    clampRows();
  } catch (e) {
    if (grid.id === 'shortsGrid') grid.closest('section').hidden = true;
    else grid.innerHTML = '<div class="empty-state"><div class="icon">📡</div><h3>No Shorts yet.</h3><p>Check back soon.</p></div>';
  }
}


/* ---------- Live "next site refresh" countdown (America/Los_Angeles) ---------- */
const REFRESH_TZ = 'America/Los_Angeles';
const REFRESH_SLOTS = [[4, 7], [10, 7], [16, 7], [22, 7]]; // 4:07, 10:07, 16:07, 22:07 PT

function tzParts(date, timeZone) {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
  const out = {};
  for (const p of fmt.formatToParts(date)) {
    if (p.type !== 'literal') out[p.type] = p.value;
  }
  return out;
}

/** Offset of timeZone at `date` instant: wallAsUTC - instant (= local minus UTC). */
function tzOffsetMs(timeZone, date) {
  const p = tzParts(date, timeZone);
  const wallAsUtc = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second);
  return wallAsUtc - date.getTime();
}

/** Convert a wall-clock time in `timeZone` to a UTC epoch ms (DST-safe). */
function zonedLocalToUtc(y, mon, d, h, mi, s, timeZone) {
  const wall = Date.UTC(y, mon - 1, d, h, mi, s);
  let guess = wall;
  for (let i = 0; i < 4; i++) {
    guess = wall - tzOffsetMs(timeZone, new Date(guess));
  }
  return guess;
}

function nextRefreshUtc(nowMs = Date.now()) {
  const p = tzParts(new Date(nowMs), REFRESH_TZ);
  const y = +p.year, mon = +p.month, d = +p.day;
  const candidates = REFRESH_SLOTS.map(([h, mi]) => zonedLocalToUtc(y, mon, d, h, mi, 0, REFRESH_TZ));
  // First slot tomorrow (handles wrap past 22:07)
  const dayEnd = zonedLocalToUtc(y, mon, d, 23, 59, 59, REFRESH_TZ);
  const tmr = tzParts(new Date(dayEnd + 2000), REFRESH_TZ);
  candidates.push(zonedLocalToUtc(+tmr.year, +tmr.month, +tmr.day, 4, 7, 0, REFRESH_TZ));
  const upcoming = candidates.filter(t => t > nowMs).sort((a, b) => a - b);
  return upcoming[0] || (candidates[0] + 86400000);
}

function formatHMS(ms) {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return [h, m, s].map(n => String(n).padStart(2, '0')).join(':');
}

function initRefreshCountdown() {
  const el = document.getElementById('refreshCountdown');
  if (!el) return;
  const tick = () => {
    const left = nextRefreshUtc() - Date.now();
    el.textContent = `Updated every 6 hours — next update in ${formatHMS(left)}`;
  };
  tick();
  setInterval(tick, 1000);
}

/* ---------- Hourly NASA / ESA / Rubin background pool ---------- */
function bgHourIndex(n) {
  if (!n) return 0;
  return Math.floor(Date.now() / 3600000) % n;
}

async function loadBackground() {
  const box = document.getElementById('bgSlides');
  if (!box) return;
  let data;
  try { data = await (await fetch('data/backgrounds.json')).json(); } catch (e) { return; }
  // Support legacy array-of-{image} and new {images:[{file,...}]}
  const list = Array.isArray(data) ? data.map(b => ({
    file: b.image || b.file,
    credit: b.credit || '',
    credit_url: b.credit_url || '',
    title: b.title || '',
  })) : (data.images || []).map(b => ({
    file: b.file || b.image,
    credit: b.credit || '',
    credit_url: b.credit_url || '',
    title: b.title || '',
  }));
  if (!list.length) return;

  // Two layers for crossfade; we swap which is "front".
  box.innerHTML = '<div class="bg-layer on"></div><div class="bg-layer"></div>';
  const layers = [...box.querySelectorAll('.bg-layer')];
  const credit = document.getElementById('bgCredit');
  let front = 0;
  let shown = -1;
  const preload = new Image();

  const apply = (idx, layerEl) => {
    const b = list[idx];
    const url = safeUrl(b.file);
    layerEl.style.backgroundImage = `url('${url}')`;
  };

  const setCredit = (idx) => {
    if (!credit) return;
    const b = list[idx];
    const label = b.credit || b.title || 'Space observatory image';
    if (b.credit_url) {
      credit.innerHTML = `Background: <a href="${safeUrl(b.credit_url)}" target="_blank" rel="noopener">${escapeHtml(label)}</a>`;
    } else {
      credit.textContent = `Background: ${label}`;
    }
  };

  const showIndex = (idx, {fade} = {fade: false}) => {
    idx = ((idx % list.length) + list.length) % list.length;
    if (idx === shown) return;
    if (!fade || shown < 0) {
      apply(idx, layers[front]);
      layers[front].classList.add('on');
      layers[1 - front].classList.remove('on');
    } else {
      const back = 1 - front;
      apply(idx, layers[back]);
      // Force reflow so opacity transition runs
      void layers[back].offsetWidth;
      layers[back].classList.add('on');
      layers[front].classList.remove('on');
      front = back;
    }
    shown = idx;
    setCredit(idx);
    // Preload the next hour's image
    const next = (idx + 1) % list.length;
    preload.src = list[next].file;
  };

  showIndex(bgHourIndex(list.length), {fade: false});

  // Check every 30s for hour rollover (and tab resumes).
  setInterval(() => showIndex(bgHourIndex(list.length), {fade: true}), 30000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) showIndex(bgHourIndex(list.length), {fade: true});
  });
}

/* ---------- Front page: show 2 rows per grid ---------- */
function clampRows() {
  ['digestGrid', 'aiGrid', 'xGrid', 'featuredGrid', 'shortsGrid'].forEach(id => {
    const g = document.getElementById(id);
    if (!g) return;
    const cols = getComputedStyle(g).gridTemplateColumns.split(' ').filter(Boolean).length || 1;
    const items = [...g.children].filter(c => !c.classList.contains('empty-state'));
    const rows = (id === 'xGrid' || id === 'featuredGrid') ? 3 : 2; // masonry X grids: extra row fills columns evenly
    items.forEach((c, i) => { c.hidden = i >= cols * rows; });
    const more = document.querySelector(`.see-all[data-for="${id}"]`);
    if (more) more.hidden = items.length <= cols * rows;
  });
  layoutMasonry();
}

/* ---------- Masonry: each card spans rows equal to its own height ---------- */
function layoutMasonry() {
  document.querySelectorAll('.social-grid, .digest-grid').forEach(g => {
    const gap = parseFloat(getComputedStyle(g).columnGap) || 20;
    [...g.children].forEach(c => {
      if (c.hidden || c.classList.contains('empty-state')) return;
      c.style.gridRowEnd = 'auto';
      c.style.marginBottom = gap + 'px';
      c.style.gridRowEnd = 'span ' + Math.ceil(c.getBoundingClientRect().height + gap);
    });
  });
}
let _mq;
const _schedMasonry = () => { cancelAnimationFrame(_mq); _mq = requestAnimationFrame(layoutMasonry); };
window.addEventListener('resize', _schedMasonry);
window.addEventListener('load', _schedMasonry);
document.addEventListener('load', e => { if (e.target.tagName === 'IMG') _schedMasonry(); }, true);
new MutationObserver(_schedMasonry).observe(document.documentElement, {childList: true, subtree: true, attributes: true, attributeFilter: ['hidden']});

/* ---------- Full news / AI pages ---------- */
async function loadFullList() {
  const grid = document.getElementById('allNewsGrid') || document.getElementById('allAiGrid');
  const isAi = grid.id === 'allAiGrid';
  let data;
  try { data = await (await fetch('data/latest.json')).json(); } catch (e) {
    grid.innerHTML = '<div class="empty-state"><div class="icon">📡</div><h3>Feed unavailable.</h3><p>Please check back shortly.</p></div>'; return;
  }
  const list = isAi ? (data.ai || []) : (data.articles || []).filter(a => !(a.tags || []).includes('AI'));
  currentArticles = list;
  const count = document.getElementById('pageCount');
  if (count) count.textContent = `${list.length} stories · updated ${data.date || ''}`;
  const render = tag => {
    grid.innerHTML = '';
    list.filter(a => !tag || (a.tags || []).includes(tag)).forEach(a => grid.appendChild(makeCard(a)));
  };
  render('');
  const chips = document.getElementById('chips');
  const tags = [...new Set(list.flatMap(a => a.tags || []))];
  if (chips && !isAi && tags.length > 1) {
    chips.hidden = false;
    chips.innerHTML = ['All', ...tags].map((t, i) => `<button type="button" class="chip${i ? '' : ' on'}" data-tag="${i ? escapeHtml(t) : ''}">${escapeHtml(t)}</button>`).join('');
    chips.addEventListener('click', e => {
      const b = e.target.closest('.chip'); if (!b) return;
      chips.querySelectorAll('.chip').forEach(c => c.classList.toggle('on', c === b));
      render(b.dataset.tag);
    });
  }
}

/* ---------- Archive ---------- */
async function loadArchive() {
  const wrap = document.getElementById('archiveList');
  if (!wrap) return;
  let data;
  try {
    const res = await fetch('data/latest.json');
    data = await res.json();
  } catch (e) {
    wrap.innerHTML = '<div class="empty-state"><div class="icon">📡</div><h3>No archive yet.</h3><p>Past digests will appear here once the feed is live.</p></div>';
    return;
  }
  const articles = (data.articles || []).slice().sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  if (!articles.length) {
    wrap.innerHTML = '<div class="empty-state"><div class="icon">📡</div><h3>No archive yet.</h3><p>Past digests will appear here once the feed is live.</p></div>';
    return;
  }
  currentArticles = articles;
  const byDate = {};
  articles.forEach(a => { (byDate[a.date || 'undated'] = byDate[a.date || 'undated'] || []).push(a); });
  const dates = Object.keys(byDate).sort().reverse();
  wrap.innerHTML = dates.map(d => `
    <div class="archive-day">
      <h3 class="archive-date"><span class="cal">${escapeHtml(d)}</span></h3>
      <div class="digest-grid">
        ${byDate[d].map(a => makeCard(a).outerHTML).join('')}
      </div>
    </div>`).join('');
}

/* ---------- util ---------- */
function escapeHtml(str) {
  if (str == null) return '';
  return String(str).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}