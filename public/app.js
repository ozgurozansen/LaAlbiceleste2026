'use strict';

/* ── State ──────────────────────────────────────────────────── */
let allMatches = [];
let sportTypes = [];
let availableLeagues = [];
let activeSport   = 1;    // overridden by config on boot
let activeLeagues = [];   // [] = all leagues; set from config on boot
let searchTerm = '';
let dateFilter = '';
let expandedIds = new Set();
let collapsedGroups = new Set();
let appConfig = {};
let lang = 'tr';

/* ── DOM refs ───────────────────────────────────────────────── */
const searchEl     = document.getElementById('search');
const dateEl       = document.getElementById('date-filter');
const refreshBtn       = document.getElementById('btn-refresh');
const toggleFiltersBtn = document.getElementById('btn-toggle-filters');
const filtersPanel     = document.getElementById('filters-panel');
const sportTabsEl     = document.getElementById('sport-tabs');
const leagueFilterEl  = document.getElementById('league-filter');
const matchesList     = document.getElementById('matches-list');
const loadingEl    = document.getElementById('loading');
const errorEl      = document.getElementById('error-msg');
const summaryEl    = document.getElementById('summary-bar');
const cacheInfoEl  = document.getElementById('cache-info');
const modal        = document.getElementById('modal');
const modalContent = document.getElementById('modal-content');
const modalClose   = document.getElementById('modal-close');
const modalBdrop   = document.getElementById('modal-backdrop');

/* ── Fetch helpers ───────────────────────────────────────────── */
async function loadMatches() {
  showLoading(true);
  hideError();

  const params = new URLSearchParams();
  params.set('sport', activeSport);
  params.set('league', activeLeagues.length ? activeLeagues.join(',') : '0');
  params.set('lang', lang);
  if (searchTerm) params.set('search', searchTerm);
  if (dateFilter) params.set('date', dateFilter);

  try {
    const res = await fetch(`/api/matches?${params}`);
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const json = await res.json();

    allMatches       = json.matches || [];
    sportTypes       = json.sportTypes || [];
    availableLeagues = json.leagues || [];

    // Update cache age
    cacheInfoEl.textContent = json.cacheAge < 5
      ? 'Fresh data'
      : `Cache: ${json.cacheAge}s ago`;

    buildSportTabs();
    buildLeagueFilter();
    populateDateFilter();
    renderMatches();
  } catch (err) {
    showError(err.message);
  } finally {
    showLoading(false);
  }
}

/* ── Render ──────────────────────────────────────────────────── */
function buildSportTabs() {
  // Always show Football first
  const all = [{ id: 0, name: 'All Sports', count: sportTypes.reduce((a,b) => a + b.count, 0) }, ...sportTypes];
  sportTabsEl.innerHTML = all
    .map(s => `<button class="sport-tab${s.id === activeSport ? ' active' : ''}" data-sport="${s.id}">
      ${s.name} <span style="opacity:.6">(${s.count})</span>
    </button>`)
    .join('');
  sportTabsEl.querySelectorAll('.sport-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      activeSport = Number(btn.dataset.sport);
      expandedIds.clear();
      loadMatches();
    });
  });
}

function buildLeagueFilter() {
  const configLeagues = appConfig.leagues || [];
  // Merge config-defined leagues with any returned by the server
  const leagueMap = {};
  availableLeagues.forEach(l => { leagueMap[l.code] = { ...l }; });
  configLeagues.forEach(l => {
    if (!leagueMap[l.code]) leagueMap[l.code] = { code: l.code, name: l.name, count: 0 };
    else leagueMap[l.code].name = l.name; // config name takes priority
  });

  const leagues = Object.values(leagueMap);
  if (leagues.length === 0) {
    leagueFilterEl.classList.add('hidden');
    return;
  }
  leagueFilterEl.classList.remove('hidden');

  const isAllActive = activeLeagues.length === 0;
  leagueFilterEl.innerHTML =
    `<span class="league-filter-label">League:</span>` +
    `<button class="league-chip all-chip${isAllActive ? ' active' : ''}" data-code="0">All</button>` +
    leagues.map(l => {
      const isActive = activeLeagues.includes(l.code);
      const countBadge = l.count ? ` <span style="opacity:.6">(${l.count})</span>` : '';
      return `<button class="league-chip${isActive ? ' active' : ''}" data-code="${l.code}">${esc(l.name)}${countBadge}</button>`;
    }).join('');

  leagueFilterEl.querySelectorAll('.league-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const code = Number(btn.dataset.code);
      if (code === 0) {
        activeLeagues = [];
      } else {
        const idx = activeLeagues.indexOf(code);
        if (idx === -1) activeLeagues.push(code);
        else activeLeagues.splice(idx, 1);
      }
      expandedIds.clear();
      loadMatches();
    });
  });
}

function populateDateFilter() {
  const dates = [...new Set(allMatches.map(m => m.date))].sort();
  const current = dateEl.value;
  dateEl.innerHTML = '<option value="">All dates</option>' +
    dates.map(d => `<option value="${d}"${d === current ? ' selected' : ''}>${d}</option>`).join('');
}

function renderMatches() {
  if (!allMatches.length) {
    matchesList.innerHTML = '<div class="empty-state">No matches found.</div>';
    summaryEl.textContent = '';
    return;
  }

  summaryEl.textContent = `${allMatches.length} match${allMatches.length !== 1 ? 'es' : ''} — click a row to expand markets`;

  matchesList.innerHTML = allMatches.map(match => buildMatchCard(match)).join('');

  // Re-attach toggle handlers
  matchesList.querySelectorAll('.match-header').forEach(header => {
    header.addEventListener('click', () => {
      const id = header.dataset.id;
      const card = header.closest('.match-card');
      if (expandedIds.has(id)) {
        expandedIds.delete(id);
        card.classList.remove('open');
      } else {
        expandedIds.add(id);
        card.classList.add('open');
      }
    });
  });

  // Restore expanded state
  expandedIds.forEach(id => {
    const card = matchesList.querySelector(`.match-card[data-id="${id}"]`);
    if (card) card.classList.add('open');
  });

  // Market group header click → collapse/expand
  matchesList.querySelectorAll('.market-group-header').forEach(header => {
    header.addEventListener('click', e => {
      e.stopPropagation();
      const group = header.closest('.market-group');
      const key = `${group.dataset.matchId}:${group.dataset.groupId}`;
      if (collapsedGroups.has(key)) {
        collapsedGroups.delete(key);
        group.classList.remove('collapsed');
      } else {
        collapsedGroups.add(key);
        group.classList.add('collapsed');
      }
    });
  });

  // Market card click → modal
  matchesList.querySelectorAll('.market-card').forEach(mc => {
    mc.addEventListener('click', e => {
      e.stopPropagation();
      const mid   = mc.dataset.matchId;
      const mktId = mc.dataset.marketId;
      openMarketModal(mid, mktId);
    });
  });
}

/* ── Collapsed preview strip ────────────────────────────────── */
const PREVIEW_DEFS = [
  { typeIds: [1],                           labelTr: 'MS',       labelEn: '1X2'      },
  { typeIds: [12],       spreadFilter: 2.5, labelTr: 'A/Ü 2.5', labelEn: 'O/U 2.5'  },
  { typeIds: [100, 101, 268, 791, 884],     labelTr: 'HND',      labelEn: 'HCP'      },
  { typeIds: [3],                           labelTr: 'ÇŞ',       labelEn: 'DC'       },
  // KG (BTTS) typeId TBD — MTID 9 is actually 2. Yarı Sonucu
  // { typeIds: [??],                        labelTr: 'KG',       labelEn: 'BTTS'     },
];

function buildMatchPreview(match) {
  const items = PREVIEW_DEFS.map(def => {
    let market = null;
    for (const tid of def.typeIds) {
      const candidates = match.markets.filter(m => m.typeId === tid);
      if (candidates.length) {
        if (def.spreadFilter != null) {
          market = candidates.find(m => Math.abs(m.spreadValue - def.spreadFilter) < 0.01) || candidates[0];
        } else {
          market = candidates[0];
        }
        break;
      }
    }
    if (!market) return null;

    const label = lang === 'tr' ? def.labelTr : def.labelEn;
    const outcomesHtml = market.outcomes.slice(0, 3).map(o => `
      <span class="prev-btn">
        <span class="prev-lbl">${esc(truncate(o.label, 5))}</span>
        <span class="prev-odds">${o.odds}</span>
      </span>`).join('');

    return `<div class="prev-mkt">
      <span class="prev-name">${esc(label)}</span>
      <span class="prev-outcomes">${outcomesHtml}</span>
    </div>`;
  }).filter(Boolean);

  if (!items.length) return '';
  return `<div class="match-preview">${items.join('')}</div>`;
}

/* ── Market grouping ─────────────────────────────────────────── */
function groupMarkets(markets) {
  const groups = appConfig.market_groups || [];
  const typeToGroup = {};
  groups.forEach((g, i) => (g.typeIds || []).forEach(id => { typeToGroup[id] = i; }));

  const buckets = groups.map(g => ({ ...g, markets: [] }));
  const other = { id: 'other', name_en: 'Other', name_tr: 'Diğer', markets: [] };
  markets.forEach(m => {
    const gi = typeToGroup[m.typeId];
    if (gi !== undefined) buckets[gi].markets.push(m);
    else other.markets.push(m);
  });
  const result = buckets.filter(b => b.markets.length > 0);
  if (other.markets.length > 0) result.push(other);
  return result;
}

function buildMarketGroup(matchId, group) {
  const key = `${matchId}:${group.id}`;
  const isCollapsed = collapsedGroups.has(key);
  const groupName = lang === 'tr' ? group.name_tr : group.name_en;
  const cardsHtml = group.markets.map(m => buildMarketCard(matchId, m)).join('');
  return `
  <div class="market-group${isCollapsed ? ' collapsed' : ''}" data-match-id="${matchId}" data-group-id="${esc(group.id)}">
    <div class="market-group-header">
      <span class="group-name">${esc(groupName)}</span>
      <span class="group-count">${group.markets.length}</span>
      <span class="group-chevron">▾</span>
    </div>
    <div class="market-group-body"><div>
      <div class="markets-grid">${cardsHtml}</div>
    </div></div>
  </div>`;
}

function buildMatchCard(match) {
  const isOpen = expandedIds.has(String(match.id));
  const grouped = groupMarkets(match.markets);
  const previewHtml = buildMatchPreview(match);

  const marketsHtml = !match.markets.length
    ? `<div class="markets-section"><p style="padding:.75rem 1rem;color:var(--muted);font-size:.82rem">No markets available</p></div>`
    : `<div class="markets-section">${grouped.map(g => buildMarketGroup(match.id, g)).join('')}</div>`;

  return `
  <div class="match-card${isOpen ? ' open' : ''}" data-id="${match.id}">
    <div class="match-header" data-id="${match.id}">
      <div class="match-header-top">
        <div class="match-time">
          <span class="date">${match.date}</span>
          <span class="time">${match.time}</span>
          <span class="date">${match.day || ''}</span>
        </div>
        <div class="match-teams">
          <div class="team-name">${esc(match.homeTeam)}</div>
          <div class="vs-sep">vs</div>
          <div class="team-name">${esc(match.awayTeam)}</div>
        </div>
        <div class="match-badges">
          ${match.isLive ? '<span class="badge badge-live">Live</span>' : ''}
          <span class="badge badge-count">${match.marketCount} mkts</span>
        </div>
        <span class="match-chevron">▾</span>
      </div>
      ${previewHtml}
    </div>
    ${marketsHtml}
  </div>`;
}

function buildMarketCard(matchId, market) {
  // Show at most 4 outcomes inline; rest visible in modal
  const displayOutcomes = market.outcomes.slice(0, 4);
  const spreadLabel = market.spreadValue !== 0
    ? `<span class="market-spread">${formatSpread(market.spreadValue)}</span>`
    : '';

  const outcomesHtml = displayOutcomes.map(o => `
    <div class="outcome-btn">
      <span class="outcome-label" title="${esc(o.label)}">${esc(truncate(o.label, 10))}</span>
      <span class="outcome-odds">${o.odds}</span>
    </div>`).join('');

  const extra = market.outcomes.length > 4
    ? `<div class="outcome-btn" style="cursor:pointer;justify-content:center">
        <span class="outcome-odds" style="color:var(--muted);font-size:.75rem">+${market.outcomes.length - 4} more</span>
       </div>`
    : '';

  return `
  <div class="market-card" data-match-id="${matchId}" data-market-id="${market.id}" title="Click to expand">
    <div class="market-name">${esc(market.typeName)}</div>
    ${spreadLabel}
    <div class="outcomes-row">${outcomesHtml}${extra}</div>
  </div>`;
}

/* ── Modal ───────────────────────────────────────────────────── */
function openMarketModal(matchId, marketId) {
  const match  = allMatches.find(m => String(m.id) === String(matchId));
  if (!match) return;
  const market = match.markets.find(m => String(m.id) === String(marketId));
  if (!market) return;

  const spreadLabel = market.spreadValue !== 0
    ? ` <span style="color:var(--yellow);font-size:.82rem">(${formatSpread(market.spreadValue)})</span>`
    : '';

  const outcomesHtml = market.outcomes.map(o => `
    <div class="modal-outcome">
      <span class="modal-outcome-label">${esc(o.label)}</span>
      <span class="modal-outcome-odds">${o.odds}</span>
    </div>`).join('');

  modalContent.innerHTML = `
    <div class="modal-match-title">${esc(match.homeTeam)} <span style="color:var(--muted)">vs</span> ${esc(match.awayTeam)}</div>
    <div style="font-size:.78rem;color:var(--muted);margin-bottom:.75rem">${match.date} • ${match.time}</div>
    <div class="modal-market-name">${esc(market.typeName)}${spreadLabel}</div>
    <div class="modal-outcomes">${outcomesHtml}</div>`;

  modal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  modal.classList.add('hidden');
  document.body.style.overflow = '';
}

/* ── Utilities ───────────────────────────────────────────────── */
function showLoading(state) {
  loadingEl.classList.toggle('hidden', !state);
  if (state) matchesList.innerHTML = '';
}
function showError(msg) {
  errorEl.textContent = `Error: ${msg}`;
  errorEl.classList.remove('hidden');
}
function hideError() { errorEl.classList.add('hidden'); }

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
function truncate(str, n) { return str.length > n ? str.slice(0, n) + '…' : str; }
function formatSpread(v) {
  if (v === 0) return '';
  return v > 0 ? `+${v}` : String(v);
}

/* ── Event listeners ─────────────────────────────────────────── */
let searchTimer;
searchEl.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchTerm = searchEl.value.trim();
    expandedIds.clear();
    loadMatches();
  }, 350);
});

dateEl.addEventListener('change', () => {
  dateFilter = dateEl.value;
  expandedIds.clear();
  loadMatches();
});

refreshBtn.addEventListener('click', () => {
  expandedIds.clear();
  loadMatches();
});

function setFiltersCollapsed(collapsed) {
  filtersPanel.classList.toggle('collapsed', collapsed);
  toggleFiltersBtn.classList.toggle('collapsed-state', collapsed);
  toggleFiltersBtn.textContent = collapsed ? '▸ Filters' : '▾ Filters';
}

// Start collapsed
setFiltersCollapsed(true);

toggleFiltersBtn.addEventListener('click', e => {
  e.stopPropagation();
  setFiltersCollapsed(!filtersPanel.classList.contains('collapsed'));
});

// Collapse when clicking outside the controls block
document.addEventListener('click', e => {
  const controls = document.querySelector('.controls');
  if (!controls.contains(e.target) && !filtersPanel.classList.contains('collapsed')) {
    setFiltersCollapsed(true);
  }
});

modalClose.addEventListener('click', closeModal);
modalBdrop.addEventListener('click', closeModal);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

document.querySelectorAll('.lang-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    lang = btn.dataset.lang;
    document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b === btn));
    expandedIds.clear();
    loadMatches();
  });
});

/* ── Boot ────────────────────────────────────────────────────── */
async function boot() {
  try {
    const res = await fetch('/api/config');
    if (res.ok) {
      appConfig = await res.json();
      const defs = appConfig.defaults || {};
      if (defs.sport != null) activeSport = defs.sport;
      if (Array.isArray(defs.leagues)) activeLeagues = [...defs.leagues];
    }
  } catch (_) { /* config load failure is non-fatal */ }
  loadMatches();
}
boot();
