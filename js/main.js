/* ============================================================
   SciVigilance — main.js
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  initNavToggle();
  initStarfield();
  loadDigest();
  loadSocial();
  initTelemetry();
  if (document.getElementById('archiveList')) loadArchive();
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
      hue: Math.random() < 0.12 ? 45 : (Math.random() < 0.5 ? 185 : 0),
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

/* ---------- X share / open helpers ---------- */
function shareOnX(article) {
  const url = article.shareUrl ||
    `https://twitter.com/intent/tweet?text=${encodeURIComponent(article.title)}&url=${encodeURIComponent(location.origin + '/' + article.url)}`;
  window.open(url, '_blank', 'noopener,width=600,height=520');
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
  articles.forEach(a => grid.appendChild(makeCard(a)));
  buildTicker(articles);
}

function showEmpty(el) {
  if (el) el.hidden = false;
}

function makeCard(a) {
  const card = document.createElement('article');
  card.className = 'card';
  const tag = (a.tags && a.tags[0]) || '';
  card.innerHTML = `
    <a href="${a.url}" class="thumb" tabindex="-1" aria-hidden="true">
      <img src="${a.image}" alt="${escapeHtml(a.title)}" loading="lazy">
      ${a.demo ? '<span class="badge-demo">Sample</span>' : ''}
      ${tag ? `<span class="badge-tag">${escapeHtml(tag)}</span>` : ''}
    </a>
    <div class="body">
      <div class="meta"><span class="time">${a.date || ''}</span><span>·</span><span>${a.readTime || '—'}</span></div>
      <h3><a href="${a.url}">${escapeHtml(a.title)}</a></h3>
      <p class="summary">${escapeHtml(a.summary || '')}</p>
      <div class="tags">${(a.tags || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}</div>
      <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:4px;">
        <a href="${a.url}" class="read">Read story <span aria-hidden="true">→</span></a>
        <button class="btn btn-ghost share-btn" data-id="${a.id}" style="padding:6px 12px;font-size:0.78rem;" aria-label="Share on X">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg> Share
        </button>
      </div>
    </div>`;
  card.querySelector('.share-btn').addEventListener('click', (e) => {
    e.preventDefault();
    const art = currentArticles.find(x => x.id === a.id);
    if (art) shareOnX(art);
  });
  return card;
}

let currentArticles = [];
function buildTicker(articles) {
  currentArticles = articles;
  const track = document.getElementById('tickerTrack');
  if (!track) return;
  const items = articles.map(a => `<span><b>${escapeHtml(a.tags && a.tags[0] || 'SIGNAL')}</b> ${escapeHtml(a.title)}</span>`).join('');
  track.innerHTML = items + items; // duplicate for seamless loop
}

/* ---------- Social ---------- */
async function loadSocial() {
  const grid = document.getElementById('socialGrid');
  const empty = document.getElementById('socialEmpty');
  if (!grid) return;
  let data;
  try {
    const res = await fetch('data/social.json');
    data = await res.json();
  } catch (e) {
    showEmpty(empty);
    return;
  }
  const items = data.highlights || [];
  if (!items.length) { showEmpty(empty); return; }
  grid.querySelectorAll('.social-card').forEach(c => c.remove());
  items.forEach(s => grid.appendChild(makeSocialCard(s)));
}

function makeSocialCard(s) {
  const el = document.createElement('div');
  el.className = 'social-card';
  el.innerHTML = `
    <div class="src">
      <span class="org">${escapeHtml(s.org)}${s.demo ? ' · Sample' : ''}</span>
      <span class="handle">${escapeHtml(s.handle || '')}</span>
    </div>
    <p class="text">${escapeHtml(s.text || '')}</p>
    <div class="foot">
      <span class="label">Highlight</span>
      <a class="ext" href="${s.link}" target="_blank" rel="noopener">View on X
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21.174 6.812a1 1 0 0 0-.292-.707l-5.586-5.586a1 1 0 0 0-1.414 1.414l3.98 3.98L1.707 19.308a1 1 0 0 0 1.414 1.414L18.38 15.534l3.98 3.98a1 1 0 0 0 1.414-1.414z"/></svg>
      </a>
    </div>`;
  return el;
}

/* ---------- Mission telemetry (flagship) ---------- */
function initTelemetry() {
  const canvas = document.getElementById('orbitalCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let w, h, dpr;

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const rect = canvas.parentElement.getBoundingClientRect();
    w = rect.width;
    h = 300;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener('resize', resize);

  const earthR = 26;
  const orbitR = () => Math.min(w * 0.4, 120);

  // Approx lunar distance model (sine wave between 356,500 and 406,700 km)
  function lunarKm(t) {
    const mean = 384400;
    var amp = 25100;
    // ~27.55 day synodic-ish period for demo smoothness
    const phase = (t / (27.55 * 864e5)) * Math.PI * 2;
    return mean + amp * Math.sin(phase);
  }

  // Mission day since a fixed epoch (Artemis era kickoff)
  const epoch = Date.UTC(2026, 0, 1);
  function missionDay(now) {
    return Math.floor((now.getTime() - epoch) / 864e5);
  }

  let angle = Math.random() * Math.PI * 2;
  let last = performance.now();

  function frame(now) {
    const dt = (now - last) / 1000;
    last = now;
    ctx.clearRect(0, 0, w, h);
    const cx = w * 0.5, cy = h * 0.5;
    const R = orbitR();

    // orbit ring
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(36,48,73,0.9)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 6]);
    ctx.stroke();
    ctx.setLineDash([]);

    // earth
    const eg = ctx.createRadialGradient(cx - 8, cy - 8, 4, cx, cy, earthR);
    eg.addColorStop(0, '#6fb7ff');
    eg.addColorStop(0.55, '#2f6fd0');
    eg.addColorStop(1, '#12356b');
    ctx.beginPath();
    ctx.arc(cx, cy, earthR, 0, Math.PI * 2);
    ctx.fillStyle = eg;
    ctx.fill();
    ctx.fillStyle = '#0b0f1a';
    ctx.font = '600 11px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText('EARTH', cx, cy + earthR + 18);

    // advance moon
    angle += dt * 0.22;
    const mx = cx + R * Math.cos(angle);
    const my = cy + R * Math.sin(angle);
    const mg = ctx.createRadialGradient(mx - 3, my - 3, 1, mx, my, 9);
    mg.addColorStop(0, '#f5f1e8');
    mg.addColorStop(1, '#9b958a');
    ctx.beginPath();
    ctx.arc(mx, my, 9, 0, Math.PI * 2);
    ctx.fillStyle = mg;
    ctx.fill();
    ctx.fillStyle = '#5d6b85';
    ctx.font = '600 10px "JetBrains Mono", monospace';
    ctx.fillText('MOON', mx, my + 24);

    // link
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(mx, my);
    ctx.strokeStyle = 'rgba(79,209,197,0.4)';
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);
    ctx.stroke();
    ctx.setLineDash([]);

    // readouts
    const now = new Date();
    const utc = now.toISOString().slice(11, 19);
    const md = document.getElementById('utcClock');
    const mday = document.getElementById('missionDay');
    const mdist = document.getElementById('lunarDist');
    if (md) md.textContent = utc + ' UTC';
    if (mday) mday.textContent = 'T+' + missionDay(now);
    if (mdist) mdist.textContent = Math.round(lunarKm(now.getTime())).toLocaleString() + ' km';

    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      requestAnimationFrame(frame);
    }
  }
  requestAnimationFrame(frame);
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
  const byDate = {};
  articles.forEach(a => { (byDate[a.date || 'undated'] = byDate[a.date || 'undated'] || []).push(a); });
  const dates = Object.keys(byDate).sort().reverse();
  wrap.innerHTML = dates.map(d => `
    <div class="archive-day">
      <h3 class="archive-date"><span class="cal">${escapeHtml(d)}</span>${data.isDemo ? ' · Sample day' : ''}</h3>
      <div class="digest-grid">
        ${byDate[d].map(a => makeCard(a)).map(c => c.outerHTML).join('')}
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