'use strict';

const _KO_FLAG_CODES = {
  'Algeria':'dz','Argentina':'ar','Australia':'au','Austria':'at','Belgium':'be',
  'Bosnia & Herzegovina':'ba','Brazil':'br','Canada':'ca','Cape Verde':'cv',
  'Colombia':'co','Croatia':'hr','Curaçao':'cw','Czech Republic':'cz','DR Congo':'cd',
  'Ecuador':'ec','Egypt':'eg','England':'gb-eng','France':'fr','Germany':'de',
  'Ghana':'gh','Haiti':'ht','Iran':'ir','Iraq':'iq','Ivory Coast':'ci','Japan':'jp',
  'Jordan':'jo','Mexico':'mx','Morocco':'ma','Netherlands':'nl','New Zealand':'nz',
  'Norway':'no','Paraguay':'py','Portugal':'pt','Qatar':'qa','Saudi Arabia':'sa',
  'Scotland':'gb-sct','Senegal':'sn','South Africa':'za','South Korea':'kr',
  'Spain':'es','Sweden':'se','Switzerland':'ch','Tunisia':'tn','Turkey':'tr',
  'USA':'us','Uruguay':'uy','Uzbekistan':'uz',
};
function _koFlag(team) {
  const code = team && _KO_FLAG_CODES[team];
  if (!code) return '';
  return `<img class="ko-flag" src="https://flagcdn.com/w20/${code}.png" alt="" loading="lazy">`;
}
function _koUserLogo(username) {
  return `<img src="/api/user/avatar/${esc(username)}" alt="" class="ko-user-logo" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'ko-user-logo-default',textContent:'👤'}))">`;
}
function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

let lang = 'tr';
let gsStats = [];
let koStats = [];
let usersMeta = {}; // username -> {supportedTeam, hasLogo}

/* ── Rendering ──────────────────────────────────────────────────────────── */

function _rankRows(items) {
  const medals = ['🥇', '🥈', '🥉'];
  return items.map((_, i) => medals[i] || `${i + 1}.`);
}

function _userCell(username, displayName) {
  const meta = usersMeta[username] || {};
  return `
    <span class="ko-lb-user">
      ${meta.hasLogo ? _koUserLogo(username) : '<span class="ko-user-logo-default">👤</span>'}
      <span>${esc(displayName || username)}</span>
      ${_koFlag(meta.supportedTeam)}
    </span>`;
}

function _renderCountTable(elId, valueKey, valueLabel) {
  const el = document.getElementById(elId);
  if (!el) return;
  const rows = [...gsStats].sort((a, b) => b[valueKey] - a[valueKey]);
  if (!rows.length) {
    el.innerHTML = `<div class="ko-empty-msg">${lang === 'tr' ? 'Henüz veri yok.' : 'No data yet.'}</div>`;
    return;
  }
  const ranks = _rankRows(rows);
  el.innerHTML = `
    <table class="ko-lb-table">
      <thead><tr>
        <th>#</th><th>${lang === 'tr' ? 'Oyuncu' : 'Player'}</th><th>${valueLabel}</th>
      </tr></thead>
      <tbody>
        ${rows.map((r, i) => `
          <tr>
            <td class="ko-lb-rank">${ranks[i]}</td>
            <td class="ko-lb-name">${_userCell(r.username, r.displayName)}</td>
            <td class="ko-lb-credit">${r[valueKey]}</td>
          </tr>`).join('')}
      </tbody>
    </table>`;
}

function _renderKoWonCount() {
  const el = document.getElementById('stats-ko-won-count');
  if (!el) return;
  const rows = [...koStats].sort((a, b) => b.wonCount - a.wonCount);
  if (!rows.length) {
    el.innerHTML = `<div class="ko-empty-msg">${lang === 'tr' ? 'Henüz veri yok.' : 'No data yet.'}</div>`;
    return;
  }
  const ranks = _rankRows(rows);
  el.innerHTML = `
    <table class="ko-lb-table">
      <thead><tr>
        <th>#</th><th>${lang === 'tr' ? 'Oyuncu' : 'Player'}</th><th>${lang === 'tr' ? 'Kazanılan Bahis' : 'Bets Won'}</th>
      </tr></thead>
      <tbody>
        ${rows.map((r, i) => `
          <tr>
            <td class="ko-lb-rank">${ranks[i]}</td>
            <td class="ko-lb-name">${_userCell(r.username, r.displayName)}</td>
            <td class="ko-lb-credit">${r.wonCount}</td>
          </tr>`).join('')}
      </tbody>
    </table>`;
}

function _renderKoBestTable(elId, valueKey, matchKey, outcomeKey, valueLabel, fmt) {
  const el = document.getElementById(elId);
  if (!el) return;
  const rows = [...koStats].filter(r => r[valueKey] != null).sort((a, b) => b[valueKey] - a[valueKey]);
  if (!rows.length) {
    el.innerHTML = `<div class="ko-empty-msg">${lang === 'tr' ? 'Henüz veri yok.' : 'No data yet.'}</div>`;
    return;
  }
  const ranks = _rankRows(rows);
  el.innerHTML = `
    <table class="ko-lb-table">
      <thead><tr>
        <th>#</th><th>${lang === 'tr' ? 'Oyuncu' : 'Player'}</th><th>${valueLabel}</th><th>${lang === 'tr' ? 'Bahis' : 'Bet'}</th>
      </tr></thead>
      <tbody>
        ${rows.map((r, i) => `
          <tr>
            <td class="ko-lb-rank">${ranks[i]}</td>
            <td class="ko-lb-name">${_userCell(r.username, r.displayName)}</td>
            <td class="ko-lb-credit">${fmt(r[valueKey])}</td>
            <td class="ko-lb-wl">${esc(r[matchKey] || '—')}<div class="stats-outcome">${esc(r[outcomeKey] || '')}</div></td>
          </tr>`).join('')}
      </tbody>
    </table>`;
}

function renderAll() {
  _renderCountTable('stats-correct-score',        'correctScore',       lang === 'tr' ? 'Doğru Skor' : 'Correct Scores');
  _renderCountTable('stats-correct-result',        'correctResult',      lang === 'tr' ? 'Doğru Sonuç' : 'Correct Results');
  _renderCountTable('stats-correct-bonus',         'correctBonus',       lang === 'tr' ? 'Doğru Bonus' : 'Correct Bonuses');
  _renderCountTable('stats-correct-player-bonus',  'correctPlayerBonus', lang === 'tr' ? 'Doğru Oyuncu Bonusu' : 'Correct Player Bonuses');
  _renderCountTable('stats-correct-minute-bonus',  'correctMinuteBonus', lang === 'tr' ? 'Doğru Dakika Bonusu' : 'Correct Minute Bonuses');
  _renderKoWonCount();
  _renderKoBestTable('stats-ko-best-payout', 'bestPayout', 'bestPayoutMatch', 'bestPayoutOutcome',
    lang === 'tr' ? 'Kredi' : 'Credit', v => `${v.toFixed(2)} la`);
  _renderKoBestTable('stats-ko-best-odds', 'bestOdds', 'bestOddsMatch', 'bestOddsOutcome',
    lang === 'tr' ? 'Oran' : 'Odds', v => v.toFixed(2));
}

/* ── Data loading ───────────────────────────────────────────────────────── */

async function loadUsersMeta() {
  try {
    const res = await fetch('/api/knockout/leaderboard');
    if (!res.ok) return;
    const json = await res.json();
    (json.leaderboard || []).forEach(u => {
      usersMeta[u.username] = { supportedTeam: u.supportedTeam, hasLogo: u.hasLogo };
    });
  } catch (_) {}
}

async function loadStats() {
  try {
    const [gsRes, koRes] = await Promise.all([
      fetch('/api/stats/groupstage'),
      fetch('/api/stats/knockout'),
    ]);
    if (gsRes.ok) gsStats = (await gsRes.json()).stats || [];
    if (koRes.ok) koStats = (await koRes.json()).stats || [];
  } catch (_) {}
  renderAll();
}

/* ── Tabs ───────────────────────────────────────────────────────────────── */

function switchStatsTab(name) {
  document.querySelectorAll('.ko-main-tabs .gs-tab').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === name);
  });
  document.getElementById('stats-tab-groupstage').classList.toggle('hidden', name !== 'groupstage');
  document.getElementById('stats-tab-knockout').classList.toggle('hidden', name !== 'knockout');
}
document.querySelectorAll('.ko-main-tabs .gs-tab').forEach(btn => {
  btn.addEventListener('click', () => switchStatsTab(btn.dataset.tab));
});

/* ── Language toggle ────────────────────────────────────────────────────── */

document.querySelectorAll('.lang-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    lang = btn.dataset.lang;
    document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b === btn));
    document.querySelectorAll('.ko-main-tabs .gs-tab').forEach(b => {
      const label = lang === 'tr' ? b.dataset.tr : b.dataset.en;
      if (label) b.textContent = label;
    });
    document.querySelectorAll('[data-tr][data-en]').forEach(el => {
      el.textContent = lang === 'tr' ? el.dataset.tr : el.dataset.en;
    });
    renderAll();
  });
});

/* ── Dynamic header offset (keeps sticky tab bar under the header) ──────── */
function _syncHeaderOffset() {
  const h = document.querySelector('header');
  if (h) document.documentElement.style.setProperty('--gs-header-offset', h.offsetHeight + 'px');
}
_syncHeaderOffset();
window.addEventListener('resize', _syncHeaderOffset);
if (typeof ResizeObserver !== 'undefined') {
  new ResizeObserver(_syncHeaderOffset).observe(document.querySelector('header'));
}

/* ── Boot ───────────────────────────────────────────────────────────────── */
(async function boot() {
  await loadUsersMeta();
  await loadStats();
})();
