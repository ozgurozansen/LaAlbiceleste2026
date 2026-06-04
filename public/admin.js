/* ═══════════════════════════════════════════════════════════════════════════
   admin.js  –  Result entry panel for FIFA World Cup 2026
   ═══════════════════════════════════════════════════════════════════════════ */

const TEAM_ALIAS = {
  'USA':                  'United States',
  'Bosnia & Herzegovina': 'Bosnia and Herzegovina',
  'Ivory Coast':          'Ivory Coast',
};
function squadTeamName(n) { return TEAM_ALIAS[n] || n; }

const S = {
  token:   localStorage.getItem('gs_token') || '',
  user:    null,
  matches: [],
  results: {},
  squads:  {},
  filter:  'all',
};

// ── Helpers ──────────────────────────────────────────────────────────────────
const esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const $  = id => document.getElementById(id);

function formatKickoff(iso) {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('tr-TR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', timeZone: 'UTC',
      timeZoneName: 'short',
    }).format(new Date(iso));
  } catch { return iso; }
}

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  return r.json();
}

// ── Auth ─────────────────────────────────────────────────────────────────────
async function checkAuth() {
  if (!S.token) return false;
  const d = await api('GET', `/api/auth/me?token=${S.token}`);
  if (d.username && d.isAdmin) {
    S.user = d;
    return true;
  }
  return false;
}

async function doLogin(e) {
  e.preventDefault();
  const uname = $('adm-uname').value.trim();
  const pw    = $('adm-pw').value;
  $('adm-login-err').textContent = '';
  const d = await api('POST', '/api/auth/login', { username: uname, password: pw });
  if (d.token) {
    if (!d.isAdmin) {
      $('adm-login-err').textContent = 'Bu hesabın admin yetkisi yok.';
      return;
    }
    S.token = d.token;
    S.user  = d;
    localStorage.setItem('gs_token', d.token);
    showPanel();
  } else {
    $('adm-login-err').textContent = d.error || 'Giriş başarısız.';
  }
}

async function doLogout() {
  await api('POST', '/api/auth/logout', { token: S.token });
  S.token = '';
  S.user  = null;
  localStorage.removeItem('gs_token');
  location.reload();
}

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadData() {
  const [mRes, rRes, sRes] = await Promise.all([
    api('GET', '/api/groupstage/matches'),
    api('GET', `/api/groupstage/results?token=${S.token}`),
    api('GET', '/api/groupstage/squads'),
  ]);
  S.matches = mRes.matches || [];
  S.results = rRes.results || {};
  S.squads  = sRes.squads  || {};
  render();
}

// ── Rendering ─────────────────────────────────────────────────────────────────
function matchVisible(m) {
  const idx = String(m.index);
  const entered = !!S.results[idx]?.scored;
  switch (S.filter) {
    case 'live':     return m.status === 'live';
    case 'finished': return m.status === 'finished';
    case 'upcoming': return m.status === 'upcoming';
    case 'entered':  return entered;
    case 'missing':  return m.status === 'finished' && !entered;
    default:         return true;
  }
}

function render() {
  const visible = S.matches.filter(matchVisible);
  $('adm-count').textContent = `${visible.length} maç gösteriliyor`;

  const container = $('adm-matches');
  container.innerHTML = '';

  if (visible.length === 0) {
    container.innerHTML = '<p style="color:#666;text-align:center;padding:2rem">Bu filtre için maç bulunamadı.</p>';
    return;
  }

  // Group by date
  const byDate = {};
  for (const m of visible) {
    const d = m.date || '?';
    (byDate[d] = byDate[d] || []).push(m);
  }

  for (const [date, matches] of Object.entries(byDate).sort()) {
    const hdr = document.createElement('div');
    hdr.style.cssText = 'font-size:.8rem;color:#888;text-transform:uppercase;letter-spacing:.08em;margin:.75rem 0 .35rem;padding-left:.25rem';
    hdr.textContent = date;
    container.appendChild(hdr);
    for (const m of matches) container.appendChild(buildCard(m));
  }
}

function buildCard(m) {
  const idx     = m.index;
  const idxS    = String(idx);
  const res     = S.results[idxS] || {};
  const entered = res.scored;

  const statusClass = m.status === 'live' ? 'live' : m.status === 'finished' ? 'finished' : 'upcoming';
  const statusLabel = m.status === 'live' ? 'Canlı' : m.status === 'finished' ? 'Bitti' : 'Yaklaşan';

  const existingScore = entered && res.score
    ? `Mevcut sonuç: <strong>${res.score.home} – ${res.score.away}</strong>`
    + (res.fhBonusAnswer ? ` &nbsp;|&nbsp; 1Y: <strong>${esc(res.fhBonusAnswer)}</strong>` : '')
    + (res.shBonusAnswer ? ` &nbsp;|&nbsp; 2Y: <strong>${esc(res.shBonusAnswer)}</strong>` : '')
    : '';

  const fhBonus = m.firstHalfBonus  || {};
  const shBonus = m.secondHalfBonus || {};

  const card = document.createElement('div');
  card.className = 'adm-card';
  card.id = `card-${idx}`;
  card.innerHTML = `
    <div class="adm-card-head">
      <div>
        <span class="adm-status-dot ${statusClass}"></span>
        <span style="font-size:.78rem;color:#999">${statusLabel}</span>
        &nbsp;
        <span class="adm-match-date">${formatKickoff(m.utcKickoff)}</span>
        &nbsp;
        <span class="adm-match-id">#${idx}</span>
      </div>
      <div class="adm-match-teams">${esc(m.team1)} <span style="color:#555">vs</span> ${esc(m.team2)}</div>
      ${m.group ? `<div style="font-size:.72rem;color:#666">${esc(m.group)}</div>` : ''}
    </div>

    <div class="adm-card-body">
      <div class="adm-existing">${existingScore}</div>

      <div class="adm-form-row">
        <div class="adm-field">
          <label>Skor</label>
          <div class="adm-score-row">
            <input type="number" class="score-input" id="hs-${idx}"
                   min="0" max="30" placeholder="Ev"
                   value="${entered && res.score ? res.score.home : ''}" />
            <span class="adm-score-sep">–</span>
            <input type="number" class="score-input" id="as-${idx}"
                   min="0" max="30" placeholder="Dep"
                   value="${entered && res.score ? res.score.away : ''}" />
          </div>
        </div>
        <div></div>

        <div class="adm-field">
          <label>1. Yarı Bonus – ${esc(fhBonus.tr || fhBonus.en || '?')}</label>
          ${buildBonusField(`fhb-${idx}`, fhBonus, m, res.fhBonusAnswer ?? '')}
          <div class="adm-bonus-hint">${esc(fhBonus.en || '')}</div>
        </div>

        <div class="adm-field">
          <label>2. Yarı Bonus – ${esc(shBonus.tr || shBonus.en || '?')}</label>
          ${buildBonusField(`shb-${idx}`, shBonus, m, res.shBonusAnswer ?? '')}
          <div class="adm-bonus-hint">${esc(shBonus.en || '')}</div>
        </div>
      </div>

      <div class="adm-actions">
        <button class="adm-save-btn" onclick="saveResult(${idx})">
          ${entered ? '✏️ Güncelle' : '💾 Kaydet'}
        </button>
        <button class="adm-fetch-btn" onclick="fetchFromApi(${idx})">
          🌐 API'den Çek
        </button>
        ${entered ? `<button class="adm-clear-btn" onclick="clearResult(${idx})">🗑 Sonucu Sil</button>` : ''}
      </div>
      <div id="msg-${idx}" class="adm-msg"></div>
    </div>
  `;
  return card;
}

// ── Custom player autocomplete ────────────────────────────────────────────────
const _acPlayers = {};

function _acRender(input) {
  const dd   = document.getElementById(input.id + '-ac');
  const data = _acPlayers[input.id];
  if (!dd || !data) return;
  const q = input.value.trim().toLowerCase();

  const homeFiltered = data.home.filter(p => !q || p.name.toLowerCase().includes(q));
  const awayFiltered = data.away.filter(p => !q || p.name.toLowerCase().includes(q));

  if (!homeFiltered.length && !awayFiltered.length) {
    dd.classList.remove('ac-open');
    return;
  }

  const mkOpt = (p, cls) =>
    `<div class="gs-ac-opt ${cls}" data-value="${esc(p.name)}" data-input="${esc(input.id)}">
       <span>${esc(p.name)}</span>
       <span class="gs-ac-meta">${esc(p.position)} · ${esc(p._team)}</span>
     </div>`;

  const homeSep = homeFiltered.length ? `<div class="gs-ac-sep">${esc(data.homeTeam)}</div>` : '';
  const awaySep = awayFiltered.length ? `<div class="gs-ac-sep">${esc(data.awayTeam)}</div>` : '';

  dd.innerHTML = homeSep + homeFiltered.map(p => mkOpt(p, 'home')).join('') +
                 awaySep + awayFiltered.map(p => mkOpt(p, 'away')).join('');

  // Position fixed relative to the input
  const rect = input.getBoundingClientRect();
  dd.style.left  = rect.left + 'px';
  dd.style.width = Math.max(rect.width, 320) + 'px';
  const spaceBelow = window.innerHeight - rect.bottom;
  if (spaceBelow >= 200) {
    dd.style.top    = (rect.bottom + 4) + 'px';
    dd.style.bottom = '';
  } else {
    dd.style.bottom = (window.innerHeight - rect.top + 4) + 'px';
    dd.style.top    = '';
  }
  dd.classList.add('ac-open');
}

let _acActiveInput = null;

function _acCloseAll() {
  document.querySelectorAll('.gs-ac-dropdown.ac-open').forEach(d => d.classList.remove('ac-open'));
  _acActiveInput = null;
}

function _acSetup() {
  document.addEventListener('input', e => {
    if (e.target.dataset.acPlayer) { _acActiveInput = e.target; _acRender(e.target); }
  });
  document.addEventListener('focusin', e => {
    if (e.target.dataset.acPlayer) { _acActiveInput = e.target; _acRender(e.target); }
  });
  document.addEventListener('focusout', e => {
    if (e.target.dataset.acPlayer) {
      setTimeout(() => {
        const dd = document.getElementById(e.target.id + '-ac');
        if (dd && dd.classList.contains('ac-open')) dd.classList.remove('ac-open');
        if (_acActiveInput === e.target) _acActiveInput = null;
      }, 150);
    }
  });
  document.addEventListener('click', e => {
    const opt = e.target.closest('.gs-ac-opt');
    if (!opt) return;
    const inp = document.getElementById(opt.dataset.input);
    if (inp) inp.value = opt.dataset.value;
    const dd = opt.closest('.gs-ac-dropdown');
    if (dd) dd.classList.remove('ac-open');
    _acActiveInput = null;
  });
  // Reposition on scroll or resize
  const _reposition = () => { if (_acActiveInput) _acRender(_acActiveInput); };
  window.addEventListener('scroll', _reposition, { passive: true, capture: true });
  window.addEventListener('resize', _reposition, { passive: true });
}

// ── Bonus field builder ─────────────────────────────────────────────────────
function buildBonusField(id, bonus, match, currentValue) {
  if (!bonus) return `<input type="text" id="${id}" />`;
  if (bonus.inputType === 'player') {
    const t1 = match.team1 || '';
    const t2 = match.team2 || '';
    const p1 = (S.squads[squadTeamName(t1)] || []).map(p => ({...p, _team: t1})).sort((a,b) => a.name.localeCompare(b.name));
    const p2 = (S.squads[squadTeamName(t2)] || []).map(p => ({...p, _team: t2})).sort((a,b) => a.name.localeCompare(b.name));
    _acPlayers[id] = { home: p1, away: p2, homeTeam: t1, awayTeam: t2 };
    return `<div style="position:relative">
              <input type="text" id="${id}" data-ac-player="1"
                     value="${esc(currentValue)}" placeholder="Oyuncu seçin…"
                     autocomplete="off" style="width:100%" />
              <div id="${id}-ac" class="gs-ac-dropdown"></div>
            </div>`;
  }
  // minute
  const placeholder = id.startsWith('fhb') ? 'Dakika (1-45+)' : 'Dakika (46-90+)';
  return `<input type="text" id="${id}" value="${esc(currentValue)}"
           placeholder="${placeholder}" style="width:100%" />`;
}

// ── Actions ───────────────────────────────────────────────────────────────────
async function saveResult(idx) {
  const hs  = $(`hs-${idx}`)?.value.trim();
  const as_ = $(`as-${idx}`)?.value.trim();
  const fhb = $(`fhb-${idx}`)?.value.trim();
  const shb = $(`shb-${idx}`)?.value.trim();
  const msg = $(`msg-${idx}`);

  if (hs === '' || as_ === '') {
    msg.className = 'adm-msg err';
    msg.textContent = 'Ev ve deplasman skoru girilmeli.';
    return;
  }

  const saveBtn = document.querySelector(`#card-${idx} .adm-save-btn`);
  saveBtn.disabled = true;
  msg.className = 'adm-msg';
  msg.textContent = 'Kaydediliyor…';

  const d = await api('POST', '/api/groupstage/result', {
    token:         S.token,
    matchIndex:    idx,
    homeScore:     parseInt(hs),
    awayScore:     parseInt(as_),
    fhBonusAnswer: fhb || null,
    shBonusAnswer: shb || null,
  });

  saveBtn.disabled = false;
  if (d.ok) {
    S.results[String(idx)] = {
      score: { home: parseInt(hs), away: parseInt(as_) },
      fhBonusAnswer: fhb || null,
      shBonusAnswer: shb || null,
      scored: true,
    };
    msg.className = 'adm-msg ok';
    msg.textContent = '✓ Kaydedildi';
    // Refresh card header to show updated existing result
    const existingDiv = document.querySelector(`#card-${idx} .adm-existing`);
    if (existingDiv) {
      existingDiv.innerHTML = `Mevcut sonuç: <strong>${hs} – ${as_}</strong>`
        + (fhb ? ` &nbsp;|&nbsp; 1Y: <strong>${esc(fhb)}</strong>` : '')
        + (shb ? ` &nbsp;|&nbsp; 2Y: <strong>${esc(shb)}</strong>` : '');
    }
    const saveBtn2 = document.querySelector(`#card-${idx} .adm-save-btn`);
    if (saveBtn2) saveBtn2.textContent = '✏️ Güncelle';
  } else {
    msg.className = 'adm-msg err';
    msg.textContent = d.error || 'Kayıt başarısız.';
  }
}

async function clearResult(idx) {
  if (!confirm(`Maç #${idx} sonucunu silmek istediğinizden emin misiniz?`)) return;
  const msg = $(`msg-${idx}`);
  msg.className = 'adm-msg';
  msg.textContent = 'Siliniyor…';

  const d = await api('POST', '/api/groupstage/result/clear', {
    token: S.token,
    matchIndex: idx,
  });

  if (d.ok) {
    delete S.results[String(idx)];
    msg.className = 'adm-msg ok';
    msg.textContent = '✓ Sonuç silindi';
    // Rebuild the card to show save form again
    const old = $(`card-${idx}`);
    if (old) {
      const m = S.matches.find(m => m.index === idx);
      if (m) old.replaceWith(buildCard(m));
    }
  } else {
    msg.className = 'adm-msg err';
    msg.textContent = d.error || 'Silinemedi.';
  }
}

async function fetchFromApi(idx) {
  const fetchBtn = document.querySelector(`#card-${idx} .adm-fetch-btn`);
  const msg      = $(`msg-${idx}`);
  fetchBtn.disabled = true;
  msg.className = 'adm-msg';
  msg.textContent = 'API\'den çekiliyor…';

  const d = await api('POST', '/api/groupstage/score', {
    token: S.token,
    matchIndex: idx,
  });

  fetchBtn.disabled = false;
  if (d.ok && d.result) {
    const r = d.result;
    $(`hs-${idx}`).value = r.home;
    $(`as-${idx}`).value = r.away;
    S.results[String(idx)] = { ...(S.results[String(idx)] || {}), score: r, scored: true };
    msg.className = 'adm-msg ok';
    msg.textContent = `✓ Çekildi: ${r.home} – ${r.away}. Bonus cevaplarını girdikten sonra Kaydet'e basın.`;
    const existingDiv = document.querySelector(`#card-${idx} .adm-existing`);
    if (existingDiv) {
      existingDiv.innerHTML = `Mevcut sonuç: <strong>${r.home} – ${r.away}</strong>`;
    }
  } else {
    msg.className = 'adm-msg err';
    msg.textContent = d.error || 'API\'den çekilemedi.';
  }
}

// ── Filter buttons ────────────────────────────────────────────────────────────
document.querySelectorAll('.adm-filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.adm-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    S.filter = btn.dataset.filter;
    render();
  });
});

// ── Show panel ────────────────────────────────────────────────────────────────
function showPanel() {
  $('adm-login-screen').classList.add('hidden');
  $('adm-panel').classList.remove('hidden');
  $('adm-user-badge').textContent = `👤 ${S.user.displayName || S.user.username}`;
  $('adm-logout-btn').addEventListener('click', doLogout);
  _acSetup();
  loadData();
}

// ── Boot ──────────────────────────────────────────────────────────────────────
$('adm-login-form').addEventListener('submit', doLogin);

(async () => {
  const ok = await checkAuth();
  if (ok) showPanel();
})();
