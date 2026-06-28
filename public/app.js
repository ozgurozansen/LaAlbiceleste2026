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

function _koFlag(team, cls = 'ko-flag') {
  const code = team && _KO_FLAG_CODES[team];
  if (!code) return '';
  return `<img class="${cls}" src="https://flagcdn.com/w20/${code}.png" alt="" loading="lazy">`;
}

/* ── State ──────────────────────────────────────────────────── */
let allMatches = [];
let sportTypes = [];
let availableLeagues = [];
let activeSport   = 1;    // overridden by config on boot
let activeLeagues = [];   // [] = all leagues; set from config on boot
let searchTerm = '';
let dateFilter = '';
let expandedIds = new Set();
let expandedGroups = new Set(); // market groups expanded by user (default: collapsed)
let appConfig = {};
let lang = 'tr';
let visitorContext = {
  timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  country: '',
  countryCode: '',
};

// Knockout betting auth state
let koToken      = localStorage.getItem('ko_token') || null;
let koUser       = null;
let koBets       = {};   // { matchId: { outcomeLabel, odds, amount, marketId, marketName, ... } }
let koCredit     = null;
let koMinBet     = 1;
let koMaxBet     = 1;
function _updateBetLimits() {
  koMaxBet = Math.max(koMinBet, Math.floor((koCredit || 0) * 0.20));
}
let koOpenModal   = null;    // { matchId, marketId } currently-open market modal
let koPendingBet  = null;    // { match, market, outcome, amount } – amount picker in progress
let koLeaderboard = [];      // [{username, displayName, credit, bets, won, lost}]



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


async function loadMatches({ silent = false } = {}) {
  if (!silent) { showLoading(true); hideError(); }

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

    if (cacheInfoEl) cacheInfoEl.textContent = '';

    if (!silent) {
      buildSportTabs();
      buildLeagueFilter();
      populateDateFilter();
      renderMatches();
    } else if (!koOpenModal && !koPendingBet) {
      renderMatches();
    }
  } catch (err) {
    if (!silent) showError(err.message);
  } finally {
    if (!silent) showLoading(false);
  }
}

async function loadVisitorContext() {
  try {
    const res = await fetch('/api/client-context');
    if (!res.ok) return;
    const json = await res.json();
    if (json.timeZone) visitorContext.timeZone = json.timeZone;
    if (json.country) visitorContext.country = json.country;
    if (json.countryCode) visitorContext.countryCode = json.countryCode;
  } catch (_) {
    // Fallback to browser timezone when IP geolocation is unavailable.
  }
}

/* ── Render ──────────────────────────────────────────────────── */
function buildSportTabs() {
  if (!sportTabsEl) return;
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
      expandedIds.clear(); expandedGroups.clear();
      loadMatches();
    });
  });
}

function buildLeagueFilter() {
  if (!leagueFilterEl) return;
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
      expandedIds.clear(); expandedGroups.clear();
      loadMatches();
    });
  });
}

function populateDateFilter() {
  if (!dateEl) return;
  const dates = [...new Set(allMatches.map(m => m.date))].sort();
  const current = dateEl.value;
  dateEl.innerHTML = `<option value="">${lang === 'tr' ? 'Tüm tarihler' : 'All dates'}</option>` +
    dates.map(d => `<option value="${d}"${d === current ? ' selected' : ''}>${d}</option>`).join('');
}

function renderMatches() {
  if (!allMatches.length) {
    matchesList.innerHTML = `<div class="empty-state">${lang === 'tr' ? 'Maç bulunamadı.' : 'No matches found.'}</div>`;
    summaryEl.textContent = '';
    return;
  }

  summaryEl.textContent = lang === 'tr'
    ? `${allMatches.length} maç — pazarları görmek için bir satıra tıklayın`
    : `${allMatches.length} match${allMatches.length !== 1 ? 'es' : ''} — click a row to expand markets`;

  const sorted = [...allMatches].sort((a, b) => (a.startTimestamp || 0) - (b.startTimestamp || 0));
  matchesList.innerHTML = sorted.map(match => buildMatchCard(match)).join('');

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

  // Market group header click → expand/collapse
  matchesList.querySelectorAll('.market-group-header').forEach(header => {
    header.addEventListener('click', e => {
      e.stopPropagation();
      const group = header.closest('.market-group');
      const key = `${group.dataset.matchId}:${group.dataset.groupId}`;
      if (expandedGroups.has(key)) {
        expandedGroups.delete(key);
        group.classList.add('collapsed');
      } else {
        expandedGroups.add(key);
        group.classList.remove('collapsed');
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
    const currentBet = koUser && koBets[String(match.id)];
    const outcomesHtml = market.outcomes.slice(0, 3).map(o => {
      const isBet = currentBet
        && String(currentBet.marketId) === String(market.id)
        && currentBet.outcomeLabel === o.label;
      return `<span class="prev-btn${isBet ? ' is-bet' : ''}">
        <span class="prev-lbl">${esc(truncate(o.label, 5))}</span>
        <span class="prev-odds">${o.odds}</span>
      </span>`;
    }).join('');

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
  const typeToOrder = {};
  groups.forEach((g, i) => {
    (g.typeIds || []).forEach((id, order) => {
      typeToGroup[id] = i;
      typeToOrder[id] = order;
    });
  });

  const buckets = groups.map(g => ({ ...g, markets: [] }));
  const other = { id: 'other', name_en: 'Other', name_tr: 'Diğer', markets: [] };
  markets.forEach(m => {
    const gi = typeToGroup[m.typeId];
    if (gi !== undefined) buckets[gi].markets.push(m);
    else other.markets.push(m);
  });
  
  // Sort markets within each bucket according to typeIds order according to typeIds order
  buckets.forEach(bucket => {
    bucket.markets.sort((a, b) => {
      const orderA = typeToOrder[a.typeId] ?? 999;
      const orderB = typeToOrder[b.typeId] ?? 999;
      if (orderA !== orderB) return orderA - orderB;
      
      // Secondary sort by spread value for markets with same typeId
      const sovA = a.spreadValue ?? 0;
      const sovB = b.spreadValue ?? 0;
      
      // For handicap markets: positive values first (1:0, 2:0, 3:0), then negative (0:1, 0:2, 0:3)
      // For over/under markets: ascending order (0.5, 1.5, 2.5, 3.5, 4.5)
      if (sovA >= 0 && sovB >= 0) return sovA - sovB;  // Both positive or zero: ascending
      if (sovA < 0 && sovB < 0) return sovB - sovA;    // Both negative: descending from 0 (so -1 before -2)
      return sovB - sovA;  // One positive, one negative: positive first
    });
  });
  
  return buckets.filter(b => b.markets.length > 0);
}

function buildMarketGroup(matchId, group) {
  const key = `${matchId}:${group.id}`;
  const isCollapsed = !expandedGroups.has(key);
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
  const isOpen    = expandedIds.has(String(match.id));
  const grouped   = groupMarkets(match.markets);
  const previewHtml = buildMatchPreview(match);
  const kickoff   = formatMatchStart(match);
  const placedBet = koUser && koBets[String(match.id)];
  const betPreviewHtml = placedBet
    ? `<div class="ko-bet-preview">✓ ${esc(placedBet.outcomeLabel)} <span style="opacity:.65">@ ${placedBet.odds} · ${esc(String(placedBet.marketName))} · ${placedBet.amount} la</span></div>`
    : '';

  const marketsHtml = !match.markets.length
    ? `<div class="markets-section"><p style="padding:.75rem 1rem;color:var(--muted);font-size:.82rem">No markets available</p></div>`
    : `<div class="markets-section">${grouped.map(g => buildMarketGroup(match.id, g)).join('')}</div>`;

  return `
  <div class="match-card${isOpen ? ' open' : ''}" data-id="${match.id}">
    <div class="match-header" data-id="${match.id}">
      <div class="match-header-top">
        <div class="match-time">
          <span class="date">${kickoff.date}</span>
          <span class="time">${kickoff.time}</span>
          <span class="date">${kickoff.zone}</span>
        </div>
        <div class="match-teams">
          <div class="team-name">${esc(lang === 'en' ? (match.homeTeamEn || match.homeTeam) : match.homeTeam)}</div>
          <div class="vs-sep">vs</div>
          <div class="team-name">${esc(lang === 'en' ? (match.awayTeamEn || match.awayTeam) : match.awayTeam)}</div>
        </div>
        <div class="match-badges">
          ${(() => {
            const st  = match.status || (match.isLive ? 'live' : 'upcoming');
            const cls = st === 'live' ? 'badge-live' : st === 'finished' ? 'badge-finished' : 'badge-upcoming';
            const lbl = st === 'live' ? (lang === 'tr' ? 'Canlı' : 'Live')
              : st === 'finished' ? (lang === 'tr' ? 'Bitti' : 'Finished')
              : (lang === 'tr' ? 'Yaklaşan' : 'Upcoming');
            return `<span class="badge ${cls}">${lbl}</span>`;
          })()}
          ${(koUser && koBets[String(match.id)]) ? '<span class="badge badge-bet">✓ Bet</span>' : ''}
          <span class="badge badge-count">${match.marketCount} mkts</span>
        </div>
        <span class="match-chevron">▾</span>
      </div>
      ${previewHtml}
      ${betPreviewHtml}
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

  const placedBet = koBets[String(matchId)];
  const betOnThisMarket = placedBet && String(placedBet.marketId) === String(market.id);

  const outcomesHtml = displayOutcomes.map(o => {
    const suspended = o.odds <= 1;
    const isBet = betOnThisMarket && placedBet.outcomeLabel === o.label;
    return `
    <div class="outcome-btn${suspended ? ' outcome-suspended' : ''}${isBet ? ' outcome-btn-bet' : ''}">
      <span class="outcome-label" title="${esc(o.label)}">${esc(truncate(o.label, 10))}</span>
      <span class="outcome-odds">${suspended ? '-' : o.odds}</span>
    </div>`;
  }).join('');

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

  const currentBet = koBets[String(matchId)];

  const outcomesHtml = market.outcomes.map(o => {
    const suspended = o.odds <= 1;
    const isCurrBet = !suspended && currentBet
      && String(currentBet.marketId) === String(market.id)
      && currentBet.outcomeLabel === o.label;
    const betLabel = isCurrBet ? `✓ ${lang === 'tr' ? 'Bahsiniz' : 'Your Bet'}` : (currentBet ? (lang === 'tr' ? 'Değiştir' : 'Replace') : (lang === 'tr' ? 'Oyna' : 'Bet'));
    const betBtn = (!suspended && koUser)
      ? `<button class="modal-bet-btn${isCurrBet ? ' is-current' : ''}" data-outcome-n="${o.n}">${betLabel}</button>`
      : '';
    return `
    <div class="modal-outcome${isCurrBet ? ' is-bet' : ''}${suspended ? ' outcome-suspended' : ''}" data-outcome-n="${o.n}">
      <span class="modal-outcome-label">${esc(o.label)}</span>
      <span class="modal-outcome-odds">${suspended ? '-' : o.odds}</span>
      ${betBtn}
    </div>`;
  }).join('');

  const kickoff = formatMatchStart(match);

  modalContent.innerHTML = `
    <div class="modal-match-title">${esc(lang === 'en' ? (match.homeTeamEn || match.homeTeam) : match.homeTeam)} <span style="color:var(--muted)">vs</span> ${esc(lang === 'en' ? (match.awayTeamEn || match.awayTeam) : match.awayTeam)}</div>
    <div style="font-size:.78rem;color:var(--muted);margin-bottom:.75rem">${kickoff.date} • ${kickoff.time} ${kickoff.zone}</div>
    <div class="modal-market-name">${esc(market.typeName)}${spreadLabel}</div>
    <div class="modal-outcomes">${outcomesHtml}</div>
    <div id="modal-footer"></div>`;

  // Attach bet-button listeners
  modalContent.querySelectorAll('.modal-bet-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const outN    = Number(btn.dataset.outcomeN);
      const outcome = market.outcomes.find(o => o.n === outN);
      if (outcome) placeBet(match, market, outcome);
    });
  });

  // Render initial footer (login hint, current-bet info, or empty)
  _renderModalFooter(String(matchId), market);

  koOpenModal = { matchId: String(matchId), marketId: String(marketId) };
  modal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  koOpenModal  = null;
  koPendingBet = null;
  modal.classList.add('hidden');
  document.body.style.overflow = '';
  const _sheet = document.getElementById('ko-bet-sheet');
  if (_sheet) { _sheet.classList.remove('active'); _sheet.innerHTML = ''; }
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

function toDateFromTimestamp(ts) {
  const n = Number(ts);
  if (!Number.isFinite(n)) return null;
  const ms = n > 1e12 ? n : n * 1000;
  const dt = new Date(ms);
  return Number.isNaN(dt.getTime()) ? null : dt;
}

function formatMatchStart(match) {
  const dt = toDateFromTimestamp(match.startTimestamp);
  if (!dt) {
    return {
      date: match.date || '',
      time: match.time || '',
      zone: visitorContext.timeZone || 'UTC',
    };
  }

  try {
    const locale = lang === 'tr' ? 'tr-TR' : 'en-GB';
    const date = new Intl.DateTimeFormat(locale, {
      month: 'short',
      day: 'numeric',
      timeZone: visitorContext.timeZone,
    }).format(dt);
    const time = new Intl.DateTimeFormat(locale, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: visitorContext.timeZone,
    }).format(dt);
    const zonePart = new Intl.DateTimeFormat(locale, {
      timeZone: visitorContext.timeZone,
      timeZoneName: 'short',
    }).formatToParts(dt).find(p => p.type === 'timeZoneName');

    return {
      date,
      time,
      zone: zonePart ? zonePart.value : visitorContext.timeZone,
    };
  } catch (_) {
    return {
      date: match.date || '',
      time: match.time || '',
      zone: visitorContext.timeZone || 'UTC',
    };
  }
}

/* ── Event listeners ─────────────────────────────────────────── */
let searchTimer;
searchEl?.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchTerm = searchEl.value.trim();
    expandedIds.clear(); expandedGroups.clear();
    loadMatches();
  }, 350);
});

dateEl?.addEventListener('change', () => {
  dateFilter = dateEl.value;
  expandedIds.clear(); expandedGroups.clear();
  loadMatches();
});

refreshBtn?.addEventListener('click', () => {
  expandedIds.clear(); expandedGroups.clear();
  loadMatches();
});

function setFiltersCollapsed(collapsed) {
  if (!filtersPanel) return;
  filtersPanel.classList.toggle('collapsed', collapsed);
  if (toggleFiltersBtn) {
    toggleFiltersBtn.classList.toggle('collapsed-state', collapsed);
    toggleFiltersBtn.textContent = collapsed ? '▸ Filters' : '▾ Filters';
  }
}

// Start collapsed
setFiltersCollapsed(true);

toggleFiltersBtn?.addEventListener('click', e => {
  e.stopPropagation();
  setFiltersCollapsed(!filtersPanel.classList.contains('collapsed'));
});

// Collapse when clicking outside the controls block
document.addEventListener('click', e => {
  const controls = document.querySelector('.controls');
  if (controls && filtersPanel && !controls.contains(e.target) && !filtersPanel.classList.contains('collapsed')) {
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
    expandedIds.clear(); expandedGroups.clear();
    loadMatches();
    renderAuthUI();
    renderKoLeaderboardFull();
    renderAllKoBets();
    document.querySelectorAll('.ko-main-tabs .gs-tab').forEach(b => {
      const label = lang === 'tr' ? b.dataset.tr : b.dataset.en;
      if (label) b.textContent = label;
    });
    // Static elements with data-tr / data-en text
    document.querySelectorAll('[data-tr][data-en]').forEach(el => {
      el.textContent = lang === 'tr' ? el.dataset.tr : el.dataset.en;
    });
    // Input placeholders
    document.querySelectorAll('[data-tr-ph]').forEach(el => {
      el.placeholder = lang === 'tr' ? el.dataset.trPh : el.dataset.enPh;
    });
    renderCouponPanel();
  });
});

/* ── Boot ────────────────────────────────────────────────────── */
async function boot() {
  await loadVisitorContext();
  try {
    const res = await fetch('/api/config');
    if (res.ok) {
      appConfig = await res.json();
      const defs = appConfig.defaults || {};
      if (defs.sport != null) activeSport = defs.sport;
      if (Array.isArray(defs.leagues)) activeLeagues = [...defs.leagues];
    }
  } catch (_) { /* config load failure is non-fatal */ }
  await koCheckAuth();
  loadKoLeaderboard();
  loadMatches();
}
boot();

/* ── Auto-poll odds every 60 s, pause when tab is hidden ─────── */
let _pollTimer = null;
function _startPoll() {
  if (_pollTimer) return;
  _pollTimer = setInterval(() => { loadMatches({ silent: true }); }, 60_000);
}
function _stopPoll() {
  clearInterval(_pollTimer);
  _pollTimer = null;
}
document.addEventListener('visibilitychange', () => {
  document.hidden ? _stopPoll() : (_startPoll(), loadMatches({ silent: true }));
});
_startPoll();

/* ── Knockout auth & betting ─────────────────────────────────── */

async function koCheckAuth() {
  if (!koToken) { renderAuthUI(); return; }
  try {
    const res = await fetch(`/api/auth/me?token=${encodeURIComponent(koToken)}`);
    if (!res.ok) { koToken = null; localStorage.removeItem('ko_token'); renderAuthUI(); return; }
    koUser = await res.json();
    const bRes = await fetch(`/api/knockout/bets?token=${encodeURIComponent(koToken)}`);
    if (bRes.ok) {
      const bJson = await bRes.json();
      koBets   = bJson.bets   || {};
      koCredit = bJson.credit;
      _updateBetLimits();
    }
  } catch (_) {}
  renderAuthUI();
}

async function koRefreshBets() {
  if (!koToken) return;
  try {
    const res = await fetch(`/api/knockout/bets?token=${encodeURIComponent(koToken)}`);
    if (!res.ok) return;
    const json = await res.json();
    koBets   = json.bets   || {};
    koCredit = json.credit;
    _updateBetLimits();
  } catch (_) {}
  renderAuthUI();
  renderCouponPanel();
}

function renderAuthUI() {
  const authEl = document.getElementById('auth-area');
  if (!authEl) return;
  if (koUser) {
    const betCount  = Object.keys(koBets).length;
    const creditTxt = koCredit !== null ? `${koCredit} la` : '';
    const logoHtml  = _koUserLogo(koUser.logoData);
    const flagHtml  = _koFlag(koUser.supportedTeam);
    authEl.innerHTML = `
      <button class="ko-user ko-user-btn" id="ko-profile-trigger" title="${lang === 'tr' ? 'Profil ayarları' : 'Profile settings'}">${logoHtml}${esc(koUser.displayName || koUser.username)}${flagHtml}</button>
      <button class="ko-btn" id="ko-logout-btn">${lang === 'tr' ? 'Çıkış' : 'Logout'}</button>`;
    authEl.querySelector('#ko-logout-btn').addEventListener('click', koLogout);
    authEl.querySelector('#ko-profile-trigger').addEventListener('click', openKoProfileModal);
    const actionEl = document.getElementById('ko-action-area');
    if (actionEl) {
      actionEl.innerHTML = `
        <span class="ko-credit" title="${lang === 'tr' ? 'Bahis kredisi' : 'Betting credits'}">${esc(creditTxt)}</span>
        <button class="ko-coupon-btn" id="ko-coupon-btn" title="${lang === 'tr' ? 'Kuponu gör' : 'View betting coupon'}">🎟 ${betCount}</button>`;
      actionEl.querySelector('#ko-coupon-btn').addEventListener('click', openCouponPanel);
    }
  } else {
    authEl.innerHTML = `<button class="ko-btn" id="ko-login-btn">${lang === 'tr' ? 'Giriş Yap' : 'Login'}</button>`;
    authEl.querySelector('#ko-login-btn').addEventListener('click', () => showLoginModal());
    const actionEl = document.getElementById('ko-action-area');
    if (actionEl) actionEl.innerHTML = '';
  }
  _syncHeaderOffset();
}

function openKoProfileModal() {
  if (!koUser) return;
  const teamSel = document.getElementById('ko-profile-team');
  if (teamSel) {
    const teams = Object.keys(_KO_FLAG_CODES).sort();
    teamSel.innerHTML = `<option value="">${lang === 'tr' ? '— Takım seçin —' : '— Select team —'}</option>` +
      teams.map(t => `<option value="${esc(t)}"${t === koUser.supportedTeam ? ' selected' : ''}>${esc(t)}</option>`).join('');
  }
  document.getElementById('ko-profile-current-pw').value = '';
  document.getElementById('ko-profile-new-pw').value = '';
  const errEl = document.getElementById('ko-profile-error');
  if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
  document.getElementById('ko-profile-modal').classList.remove('hidden');
  document.getElementById('ko-profile-current-pw').focus();
}

function closeKoProfileModal() {
  document.getElementById('ko-profile-modal').classList.add('hidden');
  document.getElementById('ko-profile-form').reset();
}

async function submitKoProfile(e) {
  e.preventDefault();
  const errEl = document.getElementById('ko-profile-error');
  errEl.classList.add('hidden');
  const currentPw  = document.getElementById('ko-profile-current-pw').value;
  const newPw      = document.getElementById('ko-profile-new-pw').value;
  const team       = document.getElementById('ko-profile-team').value;
  const logoInput  = document.getElementById('ko-profile-logo');
  let logoData = null;
  if (logoInput.files && logoInput.files[0]) {
    const file = logoInput.files[0];
    if (file.size > 200 * 1024) {
      errEl.textContent = lang === 'tr' ? 'Logo çok büyük (max 200KB)' : 'Logo too large (max 200KB)';
      errEl.classList.remove('hidden');
      return;
    }
    logoData = await new Promise(res => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.readAsDataURL(file);
    });
  }
  try {
    const resp = await fetch('/api/auth/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: koToken, currentPassword: currentPw, newPassword: newPw, supportedTeam: team, logoData }),
    });
    const d = await resp.json();
    if (!resp.ok) throw new Error(d.error || 'Error');
    if (d.token) { koToken = d.token; localStorage.setItem('ko_token', d.token); }
    koUser = { username: d.username, displayName: d.displayName, supportedTeam: d.supportedTeam || null, logoData: d.logoData || null };
    closeKoProfileModal();
    renderAuthUI();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  }
}

async function koLogout() {
  if (koToken) {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({token: koToken}),
      });
    } catch (_) {}
  }
  koToken  = null;
  koUser   = null;
  koBets   = {};
  koCredit = null;
  localStorage.removeItem('ko_token');
  renderAuthUI();
  renderMatches();
}

function showLoginModal() {
  const m = document.getElementById('login-modal');
  if (!m) return;
  m.classList.remove('hidden');
  document.body.style.overflow = 'hidden';

  const errEl    = document.getElementById('login-error');
  const unEl     = document.getElementById('login-username');
  const pwEl     = document.getElementById('login-password');
  const submitEl = document.getElementById('login-submit');

  if (errEl) { errEl.style.display = 'none'; errEl.textContent = ''; }
  if (unEl)  unEl.value = '';
  if (pwEl)  pwEl.value = '';

  // Replace element to clear old listeners
  const newSubmit = submitEl.cloneNode(true);
  submitEl.parentNode.replaceChild(newSubmit, submitEl);

  async function doLogin() {
    const username = unEl ? unEl.value.trim() : '';
    const password = pwEl ? pwEl.value : '';
    if (!username || !password) {
      if (errEl) { errEl.textContent = 'Username and password required'; errEl.style.display = 'block'; }
      return;
    }
    newSubmit.disabled = true;
    newSubmit.textContent = 'Logging in…';
    try {
      const res  = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username, password}),
      });
      const json = await res.json();
      if (!res.ok) {
        if (errEl) { errEl.textContent = json.error || 'Login failed'; errEl.style.display = 'block'; }
        newSubmit.disabled = false;
        newSubmit.textContent = 'Login';
        return;
      }
      koToken = json.token;
      koUser  = json;
      localStorage.setItem('ko_token', koToken);
      closeLoginModal();
      await koRefreshBets();
      renderMatches();
      // Refresh market modal if it was open so bet buttons appear
      if (koOpenModal) openMarketModal(koOpenModal.matchId, koOpenModal.marketId);
    } catch (_) {
      if (errEl) { errEl.textContent = 'Network error'; errEl.style.display = 'block'; }
      newSubmit.disabled = false;
      newSubmit.textContent = 'Login';
    }
  }

  newSubmit.addEventListener('click', doLogin);
  if (pwEl) pwEl.addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });
}

function closeLoginModal() {
  const m = document.getElementById('login-modal');
  if (m) m.classList.add('hidden');
  document.body.style.overflow = '';
}

function placeBet(match, market, outcome) {
  if (!koUser) { showLoginModal(); return; }

  const matchId    = String(match.id);
  const currentBet = koBets[matchId];

  // Same outcome already bet — clicking again opens the amount picker to change amount
  const existingAmount = (currentBet
    && String(currentBet.marketId) === String(market.id)
    && currentBet.outcomeLabel === outcome.label)
    ? (currentBet.amount || koMinBet)
    : koMinBet;

  koPendingBet = { match, market, outcome, amount: existingAmount };
  _renderModalFooter(matchId, market);
}

async function _confirmBet() {
  if (!koPendingBet || !koUser) return;
  const { match, market, outcome, amount } = koPendingBet;
  const matchId = String(match.id);

  const confirmBtn = document.getElementById('ko-confirm-bet-btn');
  if (confirmBtn) { confirmBtn.disabled = true; confirmBtn.textContent = 'Placing…'; }

  try {
    const res  = await fetch('/api/knockout/bet', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        token:          koToken,
        matchId:        match.id,
        matchName:      `${match.homeTeam} vs ${match.awayTeam}`,
        matchNameEn:    `${match.homeTeamEn || match.homeTeam} vs ${match.awayTeamEn || match.awayTeam}`,
        startTimestamp: match.startTimestamp,
        marketId:       market.id,
        marketName:     market.typeNameTr || market.typeName,
        marketNameEn:   market.typeNameEn || market.typeName,
        outcomeLabel:   outcome.labelTr || outcome.label,
        outcomeLabelEn: outcome.labelEn || outcome.label,
        outcomeN:       outcome.n,
        typeId:         market.typeId,
        spreadValue:    market.spreadValue,
        odds:           outcome.odds,
        amount,
      }),
    });
    const json = await res.json();
    if (!res.ok) {
      if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = '✓ Place Bet'; }
      alert(json.error || 'Failed to place bet');
      return;
    }
    koBets[matchId] = json.bet;
    koCredit        = json.credit;
    _updateBetLimits();
    koPendingBet    = null;
    renderAuthUI();
    renderCouponPanel();
    loadKoLeaderboard();
    _updateMatchBetBadge(matchId, json.bet);
    openMarketModal(matchId, String(market.id));  // refresh modal to show confirmed state
  } catch (_) {
    if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = '✓ Place Bet'; }
    alert('Network error placing bet');
  }
}

function _cancelBet() {
  koPendingBet = null;
  if (koOpenModal) _renderModalFooter(koOpenModal.matchId,
    allMatches.find(m => String(m.id) === koOpenModal.matchId)
      ?.markets.find(mk => String(mk.id) === koOpenModal.marketId));
}

/* Rebuild the modal-footer and the floating bet sheet as needed */
function _renderModalFooter(matchId, market) {
  const footerEl = document.getElementById('modal-footer');
  const sheet    = document.getElementById('ko-bet-sheet');
  if (!footerEl) return;

  const currentBet = koBets[String(matchId)];

  if (koPendingBet && market && String(koPendingBet.market.id) === String(market.id)) {
    const { outcome, amount } = koPendingBet;
    const payout = (outcome.odds * amount).toFixed(2);

    // Render confirmation in the floating bottom sheet instead of inline footer
    if (sheet) {
      sheet.innerHTML = `
        <div class="ko-sheet-handle"></div>
        <div class="ko-sheet-sel">
          ${lang === 'tr' ? 'Bahis' : 'Bet on'}: <strong>${esc(outcome.label)}</strong>
          <span style="opacity:.7"> @ ${outcome.odds}</span>
          <span class="ko-sheet-mkt"> · ${esc(market.typeName)}</span>
        </div>
        <div class="ko-amount-row">
          <span class="ko-amount-label">${lang === 'tr' ? 'Miktar:' : 'Amount:'}</span>
          <div class="ko-amount-stepper">
            <button class="ko-amount-btn" id="ko-amt-dec" ${amount <= koMinBet ? 'disabled' : ''}>−</button>
            <span class="ko-amount-val" id="ko-amt-val">${amount}</span>
            <button class="ko-amount-btn" id="ko-amt-inc" ${amount >= koMaxBet ? 'disabled' : ''}>+</button>
          </div>
          <span style="font-size:.78rem;color:var(--muted)">la (${koMinBet}–${koMaxBet})</span>
        </div>
        <div class="ko-payout-preview">${lang === 'tr' ? 'Tahmini kazanç' : 'Potential win'}: ${payout} la</div>
        <div class="ko-confirm-row">
          <button class="ko-confirm-bet-btn" id="ko-confirm-bet-btn">✓ ${lang === 'tr' ? 'Bahsi Oyna' : 'Place Bet'}</button>
          <button class="ko-cancel-bet-btn" id="ko-cancel-bet-btn">${lang === 'tr' ? 'İptal' : 'Cancel'}</button>
        </div>`;
      sheet.classList.add('active');
      sheet.querySelector('#ko-amt-dec').addEventListener('click', () => {
        if (koPendingBet && koPendingBet.amount > koMinBet) {
          koPendingBet.amount--;
          _renderModalFooter(matchId, market);
        }
      });
      sheet.querySelector('#ko-amt-inc').addEventListener('click', () => {
        if (koPendingBet && koPendingBet.amount < koMaxBet) {
          koPendingBet.amount++;
          _renderModalFooter(matchId, market);
        }
      });
      sheet.querySelector('#ko-confirm-bet-btn').addEventListener('click', _confirmBet);
      sheet.querySelector('#ko-cancel-bet-btn').addEventListener('click', _cancelBet);
    }

    footerEl.innerHTML = ''; // clear modal footer while sheet is visible

    // Highlight the pending outcome
    document.querySelectorAll('.modal-outcome').forEach(el => el.classList.remove('is-pending'));
    const pendingEl = document.querySelector(`.modal-outcome[data-outcome-n="${koPendingBet.outcome.n}"]`);
    if (pendingEl) pendingEl.classList.add('is-pending');
    return;
  }

  // No pending bet — dismiss the sheet
  if (sheet) { sheet.classList.remove('active'); sheet.innerHTML = ''; }

  // Remove any pending highlights
  document.querySelectorAll('.modal-outcome').forEach(el => el.classList.remove('is-pending'));

  if (!koUser) {
    footerEl.innerHTML = `<div class="ko-login-hint">
      <span>${lang === 'tr' ? 'Bahis yapmak için giriş yapın' : 'Login to place bets'}</span>
      <button class="ko-btn" id="modal-login-btn">${lang === 'tr' ? 'Giriş Yap' : 'Login'}</button>
    </div>`;
    footerEl.querySelector('#modal-login-btn').addEventListener('click', () => showLoginModal());
  } else if (currentBet && market && String(currentBet.marketId) !== String(market.id)) {
    footerEl.innerHTML = `<div class="ko-current-bet-info">
      ${lang === 'tr' ? 'Bu maç için bahsiniz' : 'Your bet for this game'}: <strong>${esc(currentBet.outcomeLabel)}</strong> @ ${currentBet.odds}
      <span style="opacity:.7;font-size:.78rem"> · ${esc(currentBet.marketName)} · ${currentBet.amount} la</span>
    </div>`;
  } else {
    footerEl.innerHTML = '';
  }
}

function _updateMatchBetBadge(matchId, bet) {
  const card = matchesList.querySelector(`.match-card[data-id="${matchId}"]`);
  if (!card) return;

  // Badge
  const badgesEl = card.querySelector('.match-badges');
  if (badgesEl && !badgesEl.querySelector('.badge-bet')) {
    const badge     = document.createElement('span');
    badge.className = 'badge badge-bet';
    badge.textContent = '✓ Bet';
    badgesEl.insertBefore(badge, badgesEl.querySelector('.badge-count') || null);
  }

  // Bet preview line
  const headerEl = card.querySelector('.match-header');
  if (headerEl && bet) {
    let previewEl = headerEl.querySelector('.ko-bet-preview');
    if (!previewEl) {
      previewEl = document.createElement('div');
      previewEl.className = 'ko-bet-preview';
      headerEl.appendChild(previewEl);
    }
    previewEl.innerHTML = `✓ ${esc(bet.outcomeLabel)} <span style="opacity:.65">@ ${bet.odds} · ${esc(String(bet.marketName))} · ${bet.amount} la</span>`;
  }

  // Refresh collapsed preview strip so the bet outcome is highlighted
  const match = allMatches.find(m => String(m.id) === String(matchId));
  if (match) {
    const previewStripEl = card.querySelector('.match-preview');
    if (previewStripEl) previewStripEl.outerHTML = buildMatchPreview(match);
  }

  // Highlight the placed outcome in all market cards for this match
  card.querySelectorAll('.market-card').forEach(mc => {
    mc.querySelectorAll('.outcome-btn').forEach(btn => {
      btn.classList.remove('outcome-btn-bet');
    });
    if (bet && String(mc.dataset.marketId) === String(bet.marketId)) {
      mc.querySelectorAll('.outcome-btn').forEach(btn => {
        const labelEl = btn.querySelector('.outcome-label');
        if (labelEl && labelEl.title === bet.outcomeLabel) {
          btn.classList.add('outcome-btn-bet');
          const oddsEl = btn.querySelector('.outcome-odds');
          if (oddsEl) oddsEl.style.color = '';
        }
      });
    }
  });
}

// ── Coupon panel ─────────────────────────────────────────────────────────────

function openCouponPanel() {
  const panel = document.getElementById('coupon-panel');
  const backdrop = document.getElementById('coupon-backdrop');
  if (!panel) return;
  renderCouponPanel();
  panel.classList.remove('hidden');
  if (backdrop) backdrop.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeCouponPanel() {
  const panel = document.getElementById('coupon-panel');
  const backdrop = document.getElementById('coupon-backdrop');
  if (panel) panel.classList.add('hidden');
  if (backdrop) backdrop.classList.add('hidden');
  document.body.style.overflow = '';
}

function renderCouponPanel() {
  const contentEl = document.getElementById('coupon-content');
  if (!contentEl) return;

  const betEntries = Object.entries(koBets).sort(([, a], [, b]) => (b.startTimestamp || 0) - (a.startTimestamp || 0));
  if (!betEntries.length) {
    contentEl.innerHTML = `<div class="coupon-empty">${lang === 'tr' ? 'Henüz bahis yapılmadı.<br>Başlamak için herhangi bir pazardan bir sonuç seçin.' : 'No bets placed yet.<br>Click an outcome in any market to start.'}</div>`;
    _renderCouponFooter(0, 0, 0);
    return;
  }

  contentEl.innerHTML = betEntries.map(([matchId, bet]) => {
    const potentialPayout = ((bet.odds || 1) * (bet.amount || koMinBet)).toFixed(2);
    const isSettled = bet.won !== undefined && bet.won !== null;
    const rowClass  = isSettled ? (bet.won ? ' is-won' : ' is-lost') : '';
    const statusTag = isSettled
      ? (bet.won
          ? `<span class="coupon-bet-tag coupon-bet-tag-won">✓ ${lang === 'tr' ? 'Kazandı' : 'Won'} +${bet.payout} la</span>`
          : `<span class="coupon-bet-tag coupon-bet-tag-lost">✗ ${lang === 'tr' ? 'Kaybetti' : 'Lost'}</span>`)
      : '';
    const deleteBtn = isSettled
      ? ''
      : `<button class="coupon-bet-delete" data-match-id="${esc(matchId)}" title="Remove bet">✕ ${lang === 'tr' ? 'Kaldır' : 'Remove'}</button>`;
    return `
    <div class="coupon-bet-row${rowClass}">
      <div class="coupon-bet-match">${esc((lang === 'en' && bet.matchNameEn) ? bet.matchNameEn : (bet.matchName || matchId))}</div>
      <div class="coupon-bet-outcome">${esc(lang === 'en' ? (bet.outcomeLabelEn || bet.outcomeLabel) : bet.outcomeLabel)}${statusTag}</div>
      <div class="coupon-bet-meta">
        <span class="coupon-bet-odds">×${bet.odds}</span>
        <span class="coupon-bet-amount">${bet.amount || koMinBet} la</span>
        ${!isSettled
          ? `<span class="coupon-bet-win">→ ${potentialPayout} la</span>`
          : bet.won
            ? `<span class="coupon-bet-win" style="color:var(--green)">→ ${bet.payout} la</span>`
            : `<span class="coupon-bet-win" style="color:var(--red,#e55)">→ 0 la</span>`}
      </div>
      <div style="font-size:.72rem;color:var(--muted);opacity:.7">${esc(lang === 'en' ? (bet.marketNameEn || bet.marketName || '') : (bet.marketName || ''))}</div>
      ${deleteBtn}
    </div>`;
  }).join('');

  contentEl.querySelectorAll('.coupon-bet-delete').forEach(btn => {
    btn.addEventListener('click', () => deleteKoBet(btn.dataset.matchId));
  });

  const totalStaked   = betEntries.reduce((s, [, b]) => s + (b.amount || koMinBet), 0);
  const totalReturned = betEntries.reduce((s, [, b]) => s + (b.won === true ? (b.payout || 0) : 0), 0);
  const totalPotential = betEntries.reduce((s, [, b]) => b.won === undefined ? s + (b.odds || 1) * (b.amount || koMinBet) : s, 0);
  _renderCouponFooter(totalStaked, totalPotential, totalReturned);
}

function _renderCouponFooter(staked, potential, returned) {
  const panel = document.getElementById('coupon-panel');
  if (!panel) return;
  let footerEl = panel.querySelector('.coupon-footer');
  if (!footerEl) {
    footerEl = document.createElement('div');
    footerEl.className = 'coupon-footer';
    panel.appendChild(footerEl);
  }
  const hasReturned = returned > 0;
  const isTr = lang === 'tr';
  footerEl.innerHTML = `
    <div class="coupon-footer-row">
      <span class="coupon-footer-label">${isTr ? 'Kalan Kredi' : 'Credits left'}</span>
      <span class="coupon-footer-val">${koCredit !== null ? koCredit : '—'} la</span>
    </div>
    <div class="coupon-footer-row">
      <span class="coupon-footer-label">${isTr ? 'Toplam Bahis' : 'Total staked'}</span>
      <span class="coupon-footer-val">${staked} la</span>
    </div>
    ${hasReturned ? `
    <div class="coupon-footer-row" style="color:var(--green)">
      <span class="coupon-footer-label">${isTr ? 'Kazanılan' : 'Returned (won)'}</span>
      <span class="coupon-footer-val">+${returned.toFixed(2)} la</span>
    </div>` : ''}
    ${potential > 0 ? `
    <div class="coupon-footer-row coupon-footer-total">
      <span class="coupon-footer-label">${isTr ? 'Potansiyel (açık)' : 'Potential (open)'}</span>
      <span class="coupon-footer-val">${potential.toFixed(2)} la</span>
    </div>` : ''}`;
}

async function deleteKoBet(matchId) {
  if (!koToken) return;
  try {
    const res  = await fetch('/api/knockout/bet/delete', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ token: koToken, matchId }),
    });
    const json = await res.json();
    if (!res.ok) { alert(json.error || 'Could not remove bet'); return; }
    delete koBets[matchId];
    koCredit = json.credit;
    _updateBetLimits();
    renderAuthUI();
    renderCouponPanel();
    loadKoLeaderboard();
    _clearMatchBetDisplay(matchId);
    // If the market modal for this match is open, refresh it
    if (koOpenModal && koOpenModal.matchId === String(matchId)) {
      openMarketModal(koOpenModal.matchId, koOpenModal.marketId);
    }
  } catch (_) {
    alert('Network error removing bet');
  }
}

function _clearMatchBetDisplay(matchId) {
  const card = matchesList.querySelector(`.match-card[data-id="${matchId}"]`);
  if (!card) return;
  card.querySelector('.badge-bet')?.remove();
  card.querySelector('.ko-bet-preview')?.remove();

  // Refresh collapsed preview strip to remove the bet highlight
  const match = allMatches.find(m => String(m.id) === String(matchId));
  if (match) {
    const previewStripEl = card.querySelector('.match-preview');
    if (previewStripEl) previewStripEl.outerHTML = buildMatchPreview(match);
  }

  // Remove outcome highlight from all market cards for this match
  card.querySelectorAll('.outcome-btn').forEach(btn => btn.classList.remove('outcome-btn-bet'));
}

// ── Knockout leaderboard ──────────────────────────────────────────────────────

async function loadKoLeaderboard() {
  try {
    const res  = await fetch('/api/knockout/leaderboard');
    if (!res.ok) return;
    const json = await res.json();
    koLeaderboard = json.leaderboard || [];
    renderKoLeaderboardFull();
  } catch (_) {}
}

function _koUserLogo(logoData, username) {
  if (username) {
    // Use avatar endpoint — browser caches per user, avoids repeating base64
    return `<img src="/api/user/avatar/${esc(username)}" alt="" class="ko-user-logo" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'ko-user-logo-default',textContent:'👤'}))">`;
  }
  if (!logoData) return '<span class="ko-user-logo-default">👤</span>';
  return `<img src="${esc(logoData)}" alt="" class="ko-user-logo" loading="lazy">`;
}

function renderKoLeaderboardFull() {
  const el = document.getElementById('ko-leaderboard-full');
  if (!el) return;
  if (!koLeaderboard.length) {
    el.innerHTML = `<div class="ko-empty-msg">${lang === 'tr' ? 'Henüz veri yok.' : 'No data yet.'}</div>`;
    return;
  }
  const medals = ['🥇', '🥈', '🥉'];
  const rows = koLeaderboard.map((u, i) => `
    <tr class="${koUser && u.username === koUser.username ? 'ko-lb-me' : ''}">
      <td class="ko-lb-rank">${medals[i] || `${i + 1}.`}</td>
      <td class="ko-lb-name">
        <span class="ko-lb-user">
          ${u.hasLogo ? _koUserLogo(null, u.username) : '<span class="ko-user-logo-default">👤</span>'}
          <span>${esc(u.displayName || u.username)}</span>
          ${_koFlag(u.supportedTeam)}
        </span>
      </td>
      <td class="ko-lb-credit">${u.credit} la</td>
      <td class="ko-lb-wl">${u.won}W / ${u.lost}L</td>
    </tr>`).join('');
  el.innerHTML = `
    <table class="ko-lb-table">
      <thead>
        <tr>
          <th>#</th>
          <th>${lang === 'tr' ? 'Oyuncu' : 'Player'}</th>
          <th>${lang === 'tr' ? 'Kredi' : 'Credits'}</th>
          <th>W/L</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ── All submitted KO bets ─────────────────────────────────────────────────────

let allKoBets = {};

function _koCorrectOutcome(bet, r) {
  const tid  = Number(bet.typeId  || 0);
  const n    = Number(bet.outcomeN || 0);
  const sov  = Number(bet.spreadValue || 0);
  const h = r.home, a = r.away;
  if (h == null) return null;
  const tot = h + a;
  const fr  = h > a ? 1 : h < a ? 2 : 0;
  const tr  = lang === 'tr';

  const T = (tr_s, en_s) => tr ? tr_s : en_s;
  const frLabel  = fr === 1 ? T('Ev Sahibi', 'Home Win') : fr === 2 ? T('Deplasman', 'Away Win') : T('Beraberlik', 'Draw');
  const yn       = v => v ? T('Evet', 'Yes') : T('Hayır', 'No');
  const home_s   = T('Ev Sahibi', 'Home');
  const away_s   = T('Deplasman', 'Away');
  const htH = r.htHome, htA = r.htAway;
  const h2 = htH != null ? h - htH : null;
  const a2 = htA != null ? a - htA : null;

  const _frOf = (gh, ga) => gh > ga ? T('Ev Sahibi', 'Home Win') : gh < ga ? T('Deplasman', 'Away Win') : T('Beraberlik', 'Draw');

  // ── 1X2 variants ─────────────────────────────────────────────
  if (tid === 1 || tid === 183) return `${frLabel} (${h}–${a})`;
  if (tid === 3)  return `${frLabel} (${h}–${a})`;
  if ((tid === 7 || tid === 8) && htH != null) return `${T('İY','HT')}: ${htH}–${htA} (${_frOf(htH,htA)})`;
  if (tid === 9 && h2 != null) return `${T('2Y','2H')}: ${h2}–${a2} (${_frOf(h2,a2)})`;
  if (tid === 5 && htH != null) return `${T('İY','HT')} ${htH}–${htA} → ${T('MS','FT')} ${h}–${a}`;
  if (tid === 571 && htH != null) return `${T('İY','HT')}: ${htH}–${htA}, ${T('MS','FT')}: ${h}–${a}`;

  // ── BTTS variants ─────────────────────────────────────────────
  if (tid === 38)  return `${yn(h>0 && a>0)} (${h}–${a})`;
  if (tid === 452 && htH != null) return `${T('İY','HT')}: ${htH}–${htA} (${T('KG','BTTS')}: ${yn(htH>0 && htA>0)})`;
  if (tid === 416 && htH != null) return `${T('İY','HT')}: ${htH}–${htA} (${_frOf(htH,htA)}, ${T('KG','BTTS')}: ${yn(htH>0 && htA>0)})`;
  if (tid === 599 && h2 != null)  return `${T('2Y','2H')}: ${h2}–${a2} (${T('KG','BTTS')}: ${yn(h2>0 && a2>0)})`;
  if (tid === 801 && htH != null) return `${T('1Y','1H')}: ${htH}–${htA}, ${T('2Y','2H')}: ${h2}–${a2}`;

  // ── Combination markets ───────────────────────────────────────
  if (tid === 272) return `${frLabel}, ${tot} ${T('gol','goals')}`;
  if (tid === 414) return `${frLabel}, ${T('KG','BTTS')}: ${yn(h>0 && a>0)}`;
  if (tid === 446 && sov) return `${tot} ${T('gol','goals')} (${T('çizgi','line')}: ${sov}), ${T('KG','BTTS')}: ${yn(h>0 && a>0)}`;

  // ── Over/Under ────────────────────────────────────────────────
  if ([11,12,13,810,812].includes(tid) && sov) return `${tot} ${T('gol','goals')} (${T('çizgi','line')}: ${sov})`;
  if (tid === 14 && htH != null) return `${T('1Y','1H')}: ${htH+htA} ${T('gol','goals')}`;
  if ([20,29,212,326,455,161].includes(tid) && sov) return `${home_s}: ${h} ${T('gol','goals')} (${T('çizgi','line')}: ${sov})`;
  if ([15,164,207,256,327,328,329,604].includes(tid) && sov) return `${away_s}: ${a} ${T('gol','goals')} (${T('çizgi','line')}: ${sov})`;
  if ((tid === 528 || tid === 529) && h2 != null) return `${T('1Y','1H')}: ${htH+htA} ${T('gol','goals')}, ${T('2Y','2H')}: ${h2+a2} ${T('gol','goals')}`;

  // ── Odd/Even ──────────────────────────────────────────────────
  if (tid === 49) return `${tot % 2 === 1 ? T('Tek','Odd') : T('Çift','Even')} (${tot} ${T('gol','goals')})`;
  if ([432,434,450].includes(tid) && htH != null) {
    const htTot = htH + htA;
    return `${T('1Y','1H')}: ${htTot % 2 === 1 ? T('Tek','Odd') : T('Çift','Even')} (${htTot} ${T('gol','goals')})`;
  }

  // ── Goals range / Most goals half ────────────────────────────
  if (tid === 43) return `${tot} ${T('gol','goals')}`;
  if (tid === 48 && htH != null) return `${T('1Y','1H')}: ${htH+htA} ${T('gol','goals')}, ${T('2Y','2H')}: ${h2+a2} ${T('gol','goals')}`;

  // ── Handicaps ────────────────────────────────────────────────
  if (tid === 418 && sov) return `${home_s} ${h} ${away_s} ${a} (${T('çizgi','line')}: ${sov})`;
  if (tid === 268 && sov) return `${home_s} ${h} ${away_s} ${a} (${T('çizgi','line')}: ${sov > 0 ? '+'+sov : sov})`;

  // ── Win margin ────────────────────────────────────────────────
  if (tid === 588) return `${frLabel} ${Math.abs(h-a)} ${T('fark','by')} (${h}–${a})`;

  // ── Exact scores ──────────────────────────────────────────────
  if (tid === 777) return `${h}:${a}`;
  if ((tid === 778 || tid === 779) && htH != null) return `${T('İY','HT')}: ${htH}:${htA}`;

  // ── Both halves ───────────────────────────────────────────────
  if (tid === 295 && htH != null) return `${home_s}: ${T('1Y','1H')} ${htH}, ${T('2Y','2H')} ${h2} → ${yn(htH>0 && h2>0)}`;
  if (tid === 296 && htH != null) return `${away_s}: ${T('1Y','1H')} ${htA}, ${T('2Y','2H')} ${a2} → ${yn(htA>0 && a2>0)}`;
  if ((tid === 591 || tid === 592) && htH != null) return `${T('1Y','1H')}: ${htH}–${htA}, ${T('2Y','2H')}: ${h2}–${a2}`;
  if ([584,585,586,587].includes(tid) && htH != null) return `${T('1Y','1H')}: ${htH}–${htA}, ${T('2Y','2H')}: ${h2}–${a2}`;

  // ── Clean sheets / wins to nil ────────────────────────────────
  if (tid === 214) return `${yn(a === 0)} (${away_s}: ${a} ${T('gol','goals')})`;
  if (tid === 215) return `${yn(h === 0)} (${home_s}: ${h} ${T('gol','goals')})`;
  if (tid === 589) return `${yn(fr === 1 && a === 0)} (${h}–${a})`;
  if (tid === 590) return `${yn(fr === 2 && h === 0)} (${h}–${a})`;

  // ── Who advances / shootout ───────────────────────────────────
  if (tid === 182) return `${frLabel} (${h}–${a})`;
  if (tid === 593) return `${T('MS','FT')}: ${h}–${a}`;

  // ── First to score ────────────────────────────────────────────
  if (tid === 291) return r.firstScorer ? `${T('İlk gol','First scorer')}: ${r.firstScorer}` : T('Gol yok','No goals');

  // ── Red card in match ─────────────────────────────────────────
  if (tid === 225) {
    const s = (r.redCards || []).join(', ');
    return s ? `${T('Kırmızı kart','Red card')}: ${s}` : T('Kırmızı kart yok','No red cards');
  }

  // ── Player markets ────────────────────────────────────────────
  if (tid === 701) {
    const s = (r.scorers || []).join(', ');
    return s ? `${T('Goller','Scored')}: ${s}` : T('Gol yok','No goals');
  }
  if (tid === 702) return r.firstScorer ? `${T('İlk','First')}: ${r.firstScorer}` : T('Gol yok','No goals');
  if (tid === 706) {
    const s = (r.headerScorers || []).join(', ');
    return s ? `${T('Kafa','Header')}: ${s}` : T('Kafa golü yok','No header goals');
  }
  if (tid === 708) {
    const s = (r.fkScorers || []).join(', ');
    return s ? `${T('Friki','Freekick')}: ${s}` : T('Frikik golü yok','No freekick goals');
  }
  if (tid === 707) {
    const s = (r.assisters || []).join(', ');
    return s ? `${T('Asistler','Assisted')}: ${s}` : T('Asist yok','No assists');
  }
  if (tid === 704 || tid === 710) {
    const s = (r.yellowCards || []).join(', ');
    return s ? `${T('Sarı kart','Yellow')}: ${s}` : T('Sarı kart yok','No yellow cards');
  }
  if (tid === 722) {
    const s = (r.anyCards || []).join(', ');
    return s ? `${T('Kart','Carded')}: ${s}` : T('Kart yok','No cards');
  }
  if (tid === 709) {
    const s = (r.redCards || []).join(', ');
    return s ? `${T('Kırmızı kart','Red card')}: ${s}` : T('Kırmızı kart yok','No red cards');
  }
  if (tid === 765) {
    const s = (r.scorers || []).concat(r.assisters || []).filter((v,i,a)=>a.indexOf(v)===i).join(', ');
    return s ? `${T('Gol/Asist','G/A')}: ${s}` : T('Gol veya asist yok','No goals or assists');
  }

  // ── Statistics-based markets ──────────────────────────────────────────
  const stats = r.statistics || {};
  const hs = stats.home || {};
  const as_ = stats.away || {};

  const _sideLabel = lbl => {
    const l = lbl.toLowerCase();
    return (l.includes('away') || l.includes('deplasman')) ? away_s : home_s;
  };
  const _sideStats = lbl => {
    const l = lbl.toLowerCase();
    return (l.includes('away') || l.includes('deplasman')) ? as_ : hs;
  };

  // Corners — full-match
  if ([216, 424, 338, 583, 220, 299, 601, 602, 798, 864, 867].includes(tid)) {
    const hc = hs.corners != null ? Number(hs.corners) : null;
    const ac = as_.corners != null ? Number(as_.corners) : null;
    if (hc != null) return `${T('Korner','Corners')}: ${hc}–${ac} (${T('toplam','total')} ${hc + ac})`;
  }
  // Corners — 1st half
  const h1c = r.h1Corners || {};
  if ([222, 340, 862, 799].includes(tid) && h1c.home != null)
    return `${T('1Y Korner','1H Corners')}: ${h1c.home}–${h1c.away}`;
  // First corner
  if (tid === 224 && r.firstCornerTeam != null)
    return `${T('İlk korner','First corner')}: ${r.firstCornerTeam === 1 ? home_s : away_s}`;
  // Card points / most card points
  if ([218, 301, 863, 603].includes(tid) && hs.yellowCards != null) {
    const hYel = Number(hs.yellowCards || 0), aYel = Number(as_.yellowCards || 0);
    const hRed = Number(hs.redCards    || 0), aRed = Number(as_.redCards    || 0);
    const hCp = hYel + hRed * 2, aCp = aYel + aRed * 2;
    return `${T('Kart puanı','Card pts')}: ${hCp}–${aCp} (${T('toplam','total')} ${hCp + aCp})`;
  }
  // Saves O/U
  if (tid === 803 && hs.saves != null) {
    const hSav = Number(hs.saves || 0), aSav = Number(as_.saves || 0);
    return `${T('Kurtarış','Saves')}: ${hSav}–${aSav} (${T('toplam','total')} ${hSav + aSav})`;
  }
  // Shots (home or away — determined by outcome label)
  if ([805, 806].includes(tid)) {
    const key    = tid === 805 ? 'totalShots' : 'shotsOnGoal';
    const lbl    = bet.outcomeLabel || '';
    const metric = tid === 805 ? T('şut','shots') : T('isabetli şut','shots on goal');
    const side   = _sideStats(lbl);
    const slbl   = _sideLabel(lbl);
    if (side[key] != null) return `${slbl} ${metric}: ${Number(side[key])}`;
  }
  // Offsides O/U
  if (tid === 808) {
    const lbl = bet.outcomeLabel || '';
    const val = _sideStats(lbl).offsides;
    if (val != null) return `${_sideLabel(lbl)} ${T('ofsayt','offsides')}: ${Number(val)}`;
  }
  // Fouls O/U
  if (tid === 807) {
    const lbl = bet.outcomeLabel || '';
    const val = _sideStats(lbl).fouls;
    if (val != null) return `${_sideLabel(lbl)} ${T('faul','fouls')}: ${Number(val)}`;
  }
  // Possession O/U
  if (tid === 809) {
    const lbl = bet.outcomeLabel || '';
    const val = _sideStats(lbl).possession;
    if (val != null) return `${_sideLabel(lbl)} ${T('top hakimiyeti','possession')}: ${Number(val)}%`;
  }

  // ── Universal fallback ────────────────────────────────────────
  return `${T('MS','FT')}: ${h}–${a}`;
}

async function loadAllKoBets() {
  const loadingEl = document.getElementById('ko-submitted-loading');
  if (loadingEl) loadingEl.classList.remove('hidden');
  try {
    const res  = await fetch('/api/knockout/bets/all');
    if (!res.ok) return;
    const json = await res.json();
    allKoBets = json.matches || {};
  } catch (_) {}
  finally {
    if (loadingEl) loadingEl.classList.add('hidden');
  }
}

function renderAllKoBets() {
  const container = document.getElementById('ko-submitted-bets');
  if (!container) return;
  const matchIds = Object.keys(allKoBets);
  if (!matchIds.length) {
    container.innerHTML = `<div class="ko-empty-msg">${lang === 'tr' ? 'Henüz başlamış maç yok.' : 'No started matches yet.'}</div>`;
    return;
  }
  matchIds.sort((a, b) => {
    const ta = Number(allKoBets[a].startTimestamp || 0);
    const tb = Number(allKoBets[b].startTimestamp || 0);
    return tb - ta;
  });
  const cards = matchIds.map(mId => {
    const m = allKoBets[mId];
    const bets = m.bets || [];
    const tsRaw = Number(m.startTimestamp || 0);
    const tsMs  = tsRaw > 1e10 ? tsRaw : tsRaw * 1000;
    const dateLabel = tsMs
      ? new Date(tsMs).toLocaleString(lang === 'tr' ? 'tr-TR' : 'en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
      : '';

    const r = m.result || null;
    const resultScore = r && r.home != null ? `FT: ${r.home}–${r.away}` : '';
    const sortedBets = [...bets].sort((a, b) => (a.marketName || '').localeCompare(b.marketName || ''));
    const betRows = sortedBets.length
      ? sortedBets.map(b => {
          const wonIcon = b.won === true  ? '<span class="ko-bet-result ko-bet-won">✓</span>'
                        : b.won === false ? '<span class="ko-bet-result ko-bet-lost">✗</span>'
                        : '<span class="ko-bet-result ko-bet-pending">·</span>';
          const payoutHtml = b.won === true && b.payout
            ? `<span class="ko-bet-payout">+${b.payout} la</span>` : '';
          const correctHtml = b.won === false && r
            ? (() => {
                const txt = _koCorrectOutcome(b, r);
                return txt ? `<span class="ko-bet-correct">${esc(txt)}</span>` : '';
              })()
            : '';
          const detailHtml = b.resultDetail && b.won !== undefined && b.won !== null
            ? `<span class="ko-bet-result-detail">${esc(b.resultDetail)}</span>` : '';
          return `
            <div class="ko-bet-row">
              <div class="ko-bet-user">
                <span class="ko-bet-username">${esc(b.displayName || b.username)}</span>
                ${_koFlag(b.supportedTeam)}
              </div>
              <div class="ko-bet-detail">
                <span class="ko-bet-market">${esc(lang === 'en' ? (b.marketNameEn || b.marketName || '') : (b.marketNameTr || b.marketName || ''))}</span>
                <span class="ko-bet-sep">·</span>
                <span class="ko-bet-outcome">${esc(lang === 'en' ? (b.outcomeLabelEn || b.outcomeLabel || '') : (b.outcomeLabelTr || b.outcomeLabel || ''))}</span>
                <span class="ko-bet-sep">@</span>
                <span class="ko-bet-odds">${b.odds}</span>
                <span class="ko-bet-sep">·</span>
                <span class="ko-bet-amount">${b.amount} la</span>
              </div>
              <div class="ko-bet-status">${wonIcon}${payoutHtml}${correctHtml}${detailHtml}</div>
            </div>`;
        }).join('')
      : `<div class="ko-empty-msg">${lang === 'tr' ? 'Bu maç için bahis girilmedi.' : 'No bets for this match.'}</div>`;

    return `
      <div class="ko-submitted-card">
        <div class="ko-submitted-card-header">
          <div class="ko-submitted-card-title">
            ${esc((lang === 'en' && m.nameEn) ? m.nameEn : (m.name || mId))}
            ${resultScore ? `<span class="ko-result-score">${esc(resultScore)}</span>` : ''}
          </div>
          <div class="ko-submitted-card-date">${esc(dateLabel)}</div>
        </div>
        <div class="ko-submitted-bets-list">${betRows}</div>
      </div>`;
  }).join('');

  container.innerHTML = cards;
}

// ── Knockout tab switching ────────────────────────────────────────────────────

function switchKoTab(name) {
  document.querySelectorAll('.ko-main-tabs .gs-tab').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === name);
  });
  document.getElementById('ko-tab-bets').classList.toggle('hidden', name !== 'bets');
  document.getElementById('ko-tab-submitted').classList.toggle('hidden', name !== 'submitted');
  document.getElementById('ko-tab-leaderboard').classList.toggle('hidden', name !== 'leaderboard');
  if (name === 'submitted') loadAllKoBets().then(renderAllKoBets);
  if (name === 'leaderboard') loadKoLeaderboard();
}

document.querySelectorAll('.ko-main-tabs .gs-tab').forEach(btn => {
  btn.addEventListener('click', () => switchKoTab(btn.dataset.tab));
});

document.getElementById('coupon-close')?.addEventListener('click', closeCouponPanel);
document.getElementById('coupon-backdrop')?.addEventListener('click', closeCouponPanel);

// Close login modal on backdrop click or Escape
document.getElementById('login-backdrop')?.addEventListener('click', closeLoginModal);
document.getElementById('login-modal-close')?.addEventListener('click', closeLoginModal);

// Profile modal
document.getElementById('ko-profile-backdrop')?.addEventListener('click', closeKoProfileModal);
document.getElementById('ko-profile-modal-close')?.addEventListener('click', closeKoProfileModal);
document.getElementById('ko-profile-form')?.addEventListener('submit', submitKoProfile);

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeCouponPanel(); closeLoginModal(); closeKoProfileModal(); }
});

/* ── Dynamic header offset ───────────────────────────────────────
   Keep --gs-header-offset in sync with the real header height so
   the sticky tab bar never slides under the header on mobile.    */
function _syncHeaderOffset() {
  const h = document.querySelector('header');
  if (h) document.documentElement.style.setProperty('--gs-header-offset', h.offsetHeight + 'px');
}
_syncHeaderOffset();
window.addEventListener('resize', _syncHeaderOffset);
if (typeof ResizeObserver !== 'undefined') {
  new ResizeObserver(_syncHeaderOffset).observe(document.querySelector('header'));
}
