/* ═══════════════════════════════════════════════════════════════════════════
   groupstage.js  –  FIFA World Cup 2026 Group Stage Predictions
   ═══════════════════════════════════════════════════════════════════════════ */

// ── Team name normalisation (groupstage.json ↔ squad.json) ──────────────────
const TEAM_ALIAS = {
  'USA':                     'United States',
  'Bosnia & Herzegovina':    'Bosnia and Herzegovina',
  'Ivory Coast':             'Ivory Coast',
};
function squadTeamName(n) { return TEAM_ALIAS[n] || n; }

// ── Turkish country name map ─────────────────────────────────────────────────
const TEAM_TR = {
  'Algeria':              'Cezayir',
  'Argentina':            'Arjantin',
  'Australia':            'Avustralya',
  'Austria':              'Avusturya',
  'Belgium':              'Belçika',
  'Bosnia & Herzegovina': 'Bosna-Hersek',
  'Brazil':               'Brezilya',
  'Canada':               'Kanada',
  'Cape Verde':           'Yeşil Burun Adaları',
  'Colombia':             'Kolombiya',
  'Croatia':              'Hırvatistan',
  'Czech Republic':       'Çek Cumhuriyeti',
  'DR Congo':             'Kongo Demokratik Cumhuriyeti',
  'Ecuador':              'Ekvador',
  'Egypt':                'Mısır',
  'England':              'İngiltere',
  'France':               'Fransa',
  'Germany':              'Almanya',
  'Ghana':                'Gana',
  'Iran':                 'İran',
  'Iraq':                 'Irak',
  'Ivory Coast':          'Fildişi Sahili',
  'Japan':                'Japonya',
  'Jordan':               'Ürdün',
  'Mexico':               'Meksika',
  'Morocco':              'Fas',
  'Netherlands':          'Hollanda',
  'New Zealand':          'Yeni Zelanda',
  'Norway':               'Norveç',
  'Portugal':             'Portekiz',
  'Qatar':                'Katar',
  'Saudi Arabia':         'Suudi Arabistan',
  'Scotland':             'İskoçya',
  'South Africa':         'Güney Afrika',
  'South Korea':          'Güney Kore',
  'Spain':                'İspanya',
  'Sweden':               'İsveç',
  'Switzerland':          'İsviçre',
  'Tunisia':              'Tunus',
  'Turkey':               'Türkiye',
  'USA':                  'ABD',
  'Uzbekistan':           'Özbekistan',
};
function teamName(n) { return (S.lang === 'tr' && TEAM_TR[n]) ? TEAM_TR[n] : n; }

// ── i18n ──────────────────────────────────────────────────────────────────────
const I18N = {
  tr: {
    title:          'Grup Aşaması Tahminleri',
    login:          'Giriş Yap',
    register:       'Kayıt Ol',
    logout:         'Çıkış',
    cancel:         'İptal',
    editProfile:    'Profili Düzenle',
    username:       'Kullanıcı Adı',
    password:       'Şifre',
    currentPassword:'Mevcut Şifre',
    newPassword:    'Yeni Şifre',
    newPasswordHint:'Boş bırakırsanız şifre değişmez',
    displayName:    'Görünen Ad',
    supportedTeam:  'Taraf',
    selectTeam:     'Takım seçin…',
    logoLabel:      'Logo',
    logoHint:       'Varsa logo yükleyin (opsiyonel)',
    logoTooLarge:   'Logo çok büyük (maks 2 MB)',
    logoInvalid:    'Logo okunamadı',
    profileModalTitle:'Profil Bilgilerini Düzenle',
    profileAuthHint:'Değişiklikleri kaydetmek için mevcut şifrenizi girin',
    profileSaved:   '✓ Profil güncellendi',
    profileFail:    'Profil güncellenemedi',
    currentPasswordFail:'Mevcut şifre yanlış',
    save:           'Kaydet',
    edit:           'Düzenle',
    saving:         'Kaydediliyor…',
    score:          'Skor Tahmini',
    fhBonus:        '1. Yarı Bonus',
    shBonus:        '2. Yarı Bonus',
    leaderboard:    'Sıralama',
    tab_predictions:'Tahmin Yap',
    tab_guesses:    'Girilen Tahminler',
    tab_leaderboard:'Sıralama',
    filterAll:      'Tümü',
    filterLive:     'Canlı',
    filterFinished: 'Bitti',
    filterUpcoming: 'Yaklaşan',
    noMatchesForFilter: 'Bu filtre için maç bulunamadı',
    rank:           'Sıra',
    player:         'Oyuncu',
    points:         'Puan',
    totalPts:       'Toplam',
    scorePts:       'Skor',
    resultPts:      'Sonuç',
    bonusPts:       'Bonus',
    myGuess:        'Tahminin',
    result:         'Sonuç',
    upcoming:       'Başlamadı',
    live:           'CANLI',
    finished:       'Bitti',
    notLoggedIn:    'Tahmin girmek için giriş yapın',
    guessLocked:    'Maç başladı – tahmin kilitledi',
    savedOk:        '✓ Tahmin kaydedildi',
    errorSave:      'Kayıt hatası',
    loginFail:      'Hatalı kullanıcı adı veya şifre',
    registerFail:   'Kayıt başarısız',
    noGuess:        'Tahmin girilmedi',
    loginToView:    'Tahmini görüntülemek için giriş yapın',
    enterMinute:    'Dakika girin (1-120)',
    enterMinuteFH:  'Dakika girin (1-45+)',
    enterMinuteSH:  'Dakika girin (46-90+)',
    enterMinuteStop:'Dakika girin (1-90+)',
    firstHalf:      '1. Yarı',
    secondHalf:     '2. Yarı',
    selectPlayer:   'Oyuncu seçin…',
    group:          'Grup',
    adminPanel:     'Yönetici',
    enterResult:    'Sonuç Gir',
    fhBonusAnswer:  '1. Yarı Bonus Cevabı',
    shBonusAnswer:  '2. Yarı Bonus Cevabı',
    fetchResult:    "API'den Çek",
    fetchOk:        '✓ Sonuç API\'den çekildi',
    fetchFail:      'API sonuç bulunamadı',
    home:           'Ev Sahibi',
    away:           'Deplasman',
    yourPts:        'Puanın',
    noResults:      'Henüz sonuç girilmedi',
    submittedGuesses:'Girilen Tahminler',
    noGuesses:      'Henüz tahmin girilmedi',
    noStartedMatches:'Henüz başlayan maç yok',
  },
  en: {
    title:          'Group Stage Predictions',
    login:          'Login',
    register:       'Register',
    logout:         'Logout',
    cancel:         'Cancel',
    editProfile:    'Edit Profile',
    username:       'Username',
    password:       'Password',
    currentPassword:'Current Password',
    newPassword:    'New Password',
    newPasswordHint:'Leave blank to keep your current password',
    displayName:    'Display Name',
    supportedTeam:  'Supported Team',
    selectTeam:     'Select team…',
    logoLabel:      'Logo',
    logoHint:       'Upload a logo if you have one (optional)',
    logoTooLarge:   'Logo is too large (max 2 MB)',
    logoInvalid:    'Could not read logo',
    profileModalTitle:'Edit Profile Details',
    profileAuthHint:'Enter your current password to save changes',
    profileSaved:   '✓ Profile updated',
    profileFail:    'Could not update profile',
    currentPasswordFail:'Current password is incorrect',
    save:           'Save',
    edit:           'Edit',
    saving:         'Saving…',
    score:          'Score Prediction',
    fhBonus:        '1st Half Bonus',
    shBonus:        '2nd Half Bonus',
    leaderboard:    'Leaderboard',
    tab_predictions:'Predictions',
    tab_guesses:    'Submitted Guesses',
    tab_leaderboard:'Standings',
    filterAll:      'All',
    filterLive:     'Live',
    filterFinished: 'Finished',
    filterUpcoming: 'Upcoming',
    noMatchesForFilter: 'No matches for this filter',
    rank:           'Rank',
    player:         'Player',
    points:         'Points',
    totalPts:       'Total',
    scorePts:       'Score',
    resultPts:      'Result',
    bonusPts:       'Bonus',
    myGuess:        'Your Guess',
    result:         'Result',
    upcoming:       'Upcoming',
    live:           'LIVE',
    finished:       'Finished',
    notLoggedIn:    'Login to enter predictions',
    guessLocked:    'Match started – prediction locked',
    savedOk:        '✓ Prediction saved',
    errorSave:      'Save error',
    loginFail:      'Invalid username or password',
    registerFail:   'Registration failed',
    noGuess:        'No prediction entered',
    loginToView:    'Login to view prediction',
    enterMinute:    'Enter minute (1-120)',
    enterMinuteFH:  'Enter minute (1-45+)',
    enterMinuteSH:  'Enter minute (46-90+)',
    enterMinuteStop:'Enter minute (1-90+)',
    firstHalf:      '1st Half',
    secondHalf:     '2nd Half',
    selectPlayer:   'Select player…',
    group:          'Group',
    adminPanel:     'Admin',
    enterResult:    'Enter Result',
    fhBonusAnswer:  '1st Half Bonus Answer',
    shBonusAnswer:  '2nd Half Bonus Answer',
    fetchResult:    'Fetch from API',
    fetchOk:        '✓ Result fetched from API',
    fetchFail:      'Could not fetch result from API',
    home:           'Home',
    away:           'Away',
    yourPts:        'Your Points',
    noResults:      'No results recorded yet',
    submittedGuesses:'Submitted Guesses',
    noGuesses:      'No guesses submitted yet',
    noStartedMatches:'No matches have started yet',
  },
};

// ── Application state ─────────────────────────────────────────────────────────
const S = {
  lang:    localStorage.getItem('gs_lang') || 'tr',
  token:   localStorage.getItem('gs_token') || '',
  user:    null,          // {username, displayName, isAdmin, supportedTeam, logoData}
  visitorTimeZone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  matches: [],            // enriched group-stage matches
  squads:  {},            // teamName -> [{name, position, number}]
  guesses: {},            // matchIndex(str) -> {homeScore,awayScore,fhBonus,shBonus}
  results: {},            // matchIndex(str) -> {score:{home,away}, scored}
  allGuesses: {},          // matchIndex(str) -> {status,result,guesses[]}
  leaderboard: [],
  activeGroup: 'A',
  matchFilter: 'all',
  adminMatchIdx: null,
  points: { correct_score: 5, correct_result: 3, correct_fh_bonus: 1, correct_sh_bonus: 1 },
};

const LOGO_MAX_BYTES = 2 * 1024 * 1024;

// ── Helpers ───────────────────────────────────────────────────────────────────
const t   = k  => (I18N[S.lang] || I18N.tr)[k] || k;
const $   = id => document.getElementById(id);
const el  = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls)  e.className   = cls;
  if (html) e.innerHTML   = html;
  return e;
};

function updateStickyOffsets() {
  const header = document.querySelector('header');
  const controls = $('app') ? document.querySelector('.gs-controls') : null;
  const rootStyle = document.documentElement.style;
  if (header) rootStyle.setProperty('--gs-header-offset', `${header.offsetHeight}px`);
  if (controls) rootStyle.setProperty('--gs-controls-offset', `${controls.offsetHeight}px`);
}

const TEAM_FLAG_CODES = {
  'Algeria': 'dz',
  'Argentina': 'ar',
  'Australia': 'au',
  'Austria': 'at',
  'Belgium': 'be',
  'Bosnia & Herzegovina': 'ba',
  'Brazil': 'br',
  'Canada': 'ca',
  'Cape Verde': 'cv',
  'Colombia': 'co',
  'Croatia': 'hr',
  'Curaçao': 'cw',
  'Czech Republic': 'cz',
  'DR Congo': 'cd',
  'Ecuador': 'ec',
  'Egypt': 'eg',
  'England': 'gb-eng',
  'France': 'fr',
  'Germany': 'de',
  'Ghana': 'gh',
  'Haiti': 'ht',
  'Iran': 'ir',
  'Iraq': 'iq',
  'Ivory Coast': 'ci',
  'Japan': 'jp',
  'Jordan': 'jo',
  'Mexico': 'mx',
  'Morocco': 'ma',
  'Netherlands': 'nl',
  'New Zealand': 'nz',
  'Norway': 'no',
  'Paraguay': 'py',
  'Portugal': 'pt',
  'Qatar': 'qa',
  'Saudi Arabia': 'sa',
  'Scotland': 'gb-sct',
  'Senegal': 'sn',
  'South Africa': 'za',
  'South Korea': 'kr',
  'Spain': 'es',
  'Sweden': 'se',
  'Switzerland': 'ch',
  'Tunisia': 'tn',
  'Turkey': 'tr',
  'USA': 'us',
  'Uruguay': 'uy',
  'Uzbekistan': 'uz',
};

function teamFlagCode(team) {
  return team ? (TEAM_FLAG_CODES[team] || '') : '';
}

function buildFlagMarkup(team, className) {
  const code = teamFlagCode(team);
  if (!code) return '';
  const src = `https://flagcdn.com/w20/${code}.png`;
  return `<img class="${className} gs-flag-img" src="${src}" alt="" loading="lazy" />`;
}

function showToast(msg, isError = false) {
  const toast = $('toast');
  toast.textContent = msg;
  toast.className   = 'gs-toast' + (isError ? ' gs-toast-error' : '');
  void toast.offsetWidth;
  toast.classList.add('gs-toast-show');
  setTimeout(() => toast.classList.remove('gs-toast-show'), 3200);
}

function applyLang() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  $('hdr-title').textContent = t('title');
  document.documentElement.lang = S.lang;
  document.querySelectorAll('.lang-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.lang === S.lang);
  });
}

// ── API wrappers ──────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res  = await fetch(path, opts);
  const json = await res.json();
  if (!res.ok) throw new Error(json.error || res.statusText);
  return json;
}
const GET  = path        => api('GET',  path);
const POST = (path, body) => api('POST', path, body);

// ── Auth ──────────────────────────────────────────────────────────────────────
async function checkAuth() {
  if (!S.token) return;
  try {
    const r = await GET(`/api/auth/me?token=${S.token}`);
    S.user  = r;
  } catch {
    S.token = '';
    localStorage.removeItem('gs_token');
  }
}

async function doLogin(e) {
  e.preventDefault();
  const username = $('login-username').value.trim();
  const password = $('login-password').value;
  $('login-error').classList.add('hidden');
  try {
    const r   = await POST('/api/auth/login', { username, password });
    S.token   = r.token;
    S.user    = {
      username: r.username,
      displayName: r.displayName,
      isAdmin: r.isAdmin,
      supportedTeam: r.supportedTeam || null,
      logoData: r.logoData || null,
    };
    localStorage.setItem('gs_token', r.token);
    hideAuthModal();
    await loadUserData();
    renderUserPill();
    renderCurrentGroup();
    renderLoginCTA();
  } catch (err) {
    $('login-error').textContent = t('loginFail');
    $('login-error').classList.remove('hidden');
  }
}

async function doRegister(e) {
  e.preventDefault();
  const username    = $('reg-username').value.trim();
  const displayName = $('reg-display').value.trim();
  const password    = $('reg-password').value;
  const supportedTeam = $('reg-team')?.value || '';
  const logoInput = $('reg-logo');
  $('register-error').classList.add('hidden');
  try {
    let logoData = null;
    if (logoInput && logoInput.files && logoInput.files[0]) {
      const file = logoInput.files[0];
      if (file.size > LOGO_MAX_BYTES) {
        throw new Error(t('logoTooLarge'));
      }
      logoData = await readLogoFile(file);
    }
    const r   = await POST('/api/auth/register', {
      username,
      displayName,
      password,
      supportedTeam: supportedTeam || null,
      logoData,
    });
    S.token   = r.token;
    S.user    = {
      username: r.username,
      displayName: r.displayName,
      isAdmin: r.isAdmin,
      supportedTeam: r.supportedTeam || null,
      logoData: r.logoData || null,
    };
    localStorage.setItem('gs_token', r.token);
    hideAuthModal();
    await loadUserData();
    renderUserPill();
    renderCurrentGroup();
    renderLoginCTA();
  } catch (err) {
    $('register-error').textContent = err.message || t('registerFail');
    $('register-error').classList.remove('hidden');
  }
}

function readLogoFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error(t('logoInvalid')));
    reader.readAsDataURL(file);
  });
}

function doLogout() {
  if (S.token) POST('/api/auth/logout', { token: S.token }).catch(() => {});
  S.token = '';
  S.user  = null;
  S.guesses = {};
  localStorage.removeItem('gs_token');
  renderUserPill();
  renderCurrentGroup();
  renderLoginCTA();
}

// ── Modal helpers ─────────────────────────────────────────────────────────────
function showAuthModal() {
  $('auth-modal').classList.remove('hidden');
  $('login-username').focus();
}
function hideAuthModal() {
  $('auth-modal').classList.add('hidden');
  $('login-form').reset();
  $('register-form').reset();
}

function showProfileModal() {
  if (!S.user) return;
  hideAuthModal();
  populateTeamSelect('profile-team', S.user.supportedTeam || '');
  $('profile-current-password').value = '';
  $('profile-new-password').value = '';
  $('profile-logo').value = '';
  $('profile-error').classList.add('hidden');
  $('profile-modal').classList.remove('hidden');
  $('profile-current-password').focus();
}

function hideProfileModal() {
  $('profile-modal').classList.add('hidden');
  $('profile-form').reset();
  $('profile-logo').value = '';
}

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadMatches() {
  const r    = await GET('/api/groupstage/matches');
  S.matches  = r.matches || [];
  if (r.points) S.points = r.points;
}

async function loadSquads() {
  const r  = await GET('/api/groupstage/squads');
  S.squads = r.squads || {};
}

async function loadUserData() {
  if (!S.token) return;
  const [gR, rR] = await Promise.all([
    GET(`/api/groupstage/guesses?token=${S.token}`),
    GET(`/api/groupstage/results?token=${S.token}`),
  ]);
  S.guesses = gR.guesses || {};
  S.results = rR.results || {};
}

async function loadLeaderboard() {
  const r      = await GET('/api/groupstage/leaderboard');
  S.leaderboard = r.leaderboard || [];
}

async function loadAllGuesses() {
  const r = await GET('/api/groupstage/guesses/all');
  S.allGuesses = r.matches || {};
}

async function loadVisitorContext() {
  try {
    const r = await GET('/api/client-context');
    if (r.timeZone) S.visitorTimeZone = r.timeZone;
  } catch (_) {
    // Fallback to browser timezone when IP geolocation is unavailable.
  }
}

// ── Groups list ───────────────────────────────────────────────────────────────
function groups() {
  return [...new Set(S.matches.map(m => m.group))].sort();
}

// ── Match helpers ─────────────────────────────────────────────────────────────
function matchStatus(m) {
  // Re-evaluate client-side using utcKickoff so status is always current
  if (!m.utcKickoff) return 'upcoming';
  const ko  = new Date(m.utcKickoff);
  const now = new Date();
  if (now < ko)                              return 'upcoming';
  if (now < new Date(ko.getTime() + 150 * 60000)) return 'live';
  return 'finished';
}

function formatKickoff(m) {
  if (!m.utcKickoff) return `${m.date} ${m.time}`;
  try {
    return new Intl.DateTimeFormat(S.lang === 'tr' ? 'tr-TR' : 'en-GB', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
      timeZone: S.visitorTimeZone,
      timeZoneName: 'short',
    }).format(new Date(m.utcKickoff));
  } catch { return `${m.date} ${m.time}`; }
}

// ── Custom player autocomplete ────────────────────────────────────────────────
const _acPlayers = {}; // inputId -> { home: [{name,position}], away: [...], homeTeam, awayTeam }

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
    `<div class="gs-ac-opt ${cls}" data-value="${escHtml(p.name)}" data-input="${escHtml(input.id)}">
       <span>${escHtml(p.name)}</span>
       <span class="gs-ac-meta">${p.position} · ${escHtml(teamName(p._team))}</span>
     </div>`;

  const homeSep = homeFiltered.length ? `<div class="gs-ac-sep">${escHtml(teamName(data.homeTeam))}</div>` : '';
  const awaySep = awayFiltered.length ? `<div class="gs-ac-sep">${escHtml(teamName(data.awayTeam))}</div>` : '';

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

// ── Bonus input builder ───────────────────────────────────────────────────────
function buildBonusInput(bonus, matchIdx, half, currentValue) {
  if (!bonus) return '';
  const id        = `bonus-${half}-${matchIdx}`;
  const isPlayer  = bonus.inputType === 'player';
  const label     = S.lang === 'tr' ? bonus.tr : bonus.en;
  const halfLabel = half === 'fh' ? t('firstHalf') : t('secondHalf');

  if (isPlayer) {
    const t1 = S.matches[matchIdx]?.team1 || '';
    const t2 = S.matches[matchIdx]?.team2 || '';
    const p1 = (S.squads[squadTeamName(t1)] || []).map(p => ({...p, _team: t1})).sort((a,b) => a.name.localeCompare(b.name));
    const p2 = (S.squads[squadTeamName(t2)] || []).map(p => ({...p, _team: t2})).sort((a,b) => a.name.localeCompare(b.name));
    _acPlayers[id] = { home: p1, away: p2, homeTeam: t1, awayTeam: t2 };
    const val = escHtml(currentValue || '');
    return `
      <div class="gs-bonus-group">
        <label class="gs-bonus-label" for="${id}">
          <span class="gs-bonus-badge">${halfLabel}</span>
          ${escHtml(label)}
        </label>
        <div class="gs-player-input-wrap">
          <input type="text" id="${id}" class="gs-player-input"
                 data-ac-player="1" value="${val}"
                 placeholder="${t('selectPlayer')}" autocomplete="off" />
          <div id="${id}-ac" class="gs-ac-dropdown"></div>
        </div>
      </div>`;
  } else {
    const val = currentValue !== undefined && currentValue !== null ? currentValue : '';
    const isStoppageTime = bonus.tr === 'Oynanmayan süre' || bonus.en === 'Stoppage time';
    const minutePlaceholder = isStoppageTime
      ? t('enterMinuteStop')
      : (half === 'fh' ? t('enterMinuteFH') : t('enterMinuteSH'));
    return `
      <div class="gs-bonus-group">
        <label class="gs-bonus-label" for="${id}">
          <span class="gs-bonus-badge">${halfLabel}</span>
          ${escHtml(label)}
        </label>
        <input type="number" id="${id}" class="gs-minute-input"
               min="0" max="200" value="${val}"
               placeholder="${minutePlaceholder}" />
      </div>`;
  }
}

function escHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function getParticipatingTeams() {
  const teams = new Set();
  S.matches.forEach(m => {
    if (m.group) {
      if (m.team1) teams.add(m.team1);
      if (m.team2) teams.add(m.team2);
    }
  });
  return [...teams].sort((a, b) => teamName(a).localeCompare(teamName(b)));
}

function populateTeamSelect(selectId = 'reg-team', selectedTeam) {
  const select = $(selectId);
  if (!select) return;
  const teams = getParticipatingTeams();
  const current = selectedTeam ?? select.value;
  const options = teams.map(team =>
    `<option value="${escHtml(team)}">${escHtml(teamName(team))}</option>`
  ).join('');
  select.innerHTML = `<option value="">${t('selectTeam')}</option>${options}`;
  if (current) select.value = current;
}

function buildLogoMarkup(logoData, imgClass, defaultClass) {
  if (logoData) {
    return `<img class="${imgClass}" src="${logoData}" alt="" />`;
  }
  return `<span class="${imgClass} ${defaultClass}">⚽</span>`;
}

// ── Points badge ─────────────────────────────────────────────────────────────
function pointsBadge(pts) {
  if (!pts) return '';
  const total = pts.total;
  const cls   = total <= 0 ? 'gs-pts-red' : total <= 3 ? 'gs-pts-yellow' : 'gs-pts-green';
  return `<span class="gs-pts-badge ${cls}">+${total} ${t('totalPts')}</span>`;
}

// ── Match card renderer ───────────────────────────────────────────────────────
function renderMatchCard(m) {
  const idx     = m.index;
  const idxS    = String(idx);
  const status  = matchStatus(m);
  const guess   = S.guesses[idxS];
  const res     = S.results[idxS];
  const isLocked = (status === 'live' || status === 'finished') || !!res?.score;

  // Compute current user's points if result is known
  let pts = null;
  if (res?.score && guess) {
    pts = calcPoints(guess, res.score, res.fhBonusAnswer, res.shBonusAnswer);
  }

  const fhBonus = m.firstHalfBonus;
  const shBonus = m.secondHalfBonus;
  const fhLabel = fhBonus ? (S.lang === 'tr' ? fhBonus.tr : fhBonus.en) : '';
  const shLabel = shBonus ? (S.lang === 'tr' ? shBonus.tr : shBonus.en) : '';

  const statusCls = { upcoming: 'gs-status-upcoming', live: 'gs-status-live', finished: 'gs-status-finished' }[status];
  const statusLabel = t(status);

  // ── Score + bonus display (locked view) ──────────────────────────────────
  let lockedContent = '';
  if (isLocked) {
    const myScore = guess
      ? `${guess.homeScore} – ${guess.awayScore}`
      : `<em>${t(S.user ? 'noGuess' : 'loginToView')}</em>`;
    const resScore = res?.score ? `<strong>${res.score.home} – ${res.score.away}</strong>` : '? – ?';
    const myFh  = guess?.fhBonus  ?? '–';
    const mySh  = guess?.shBonus  ?? '–';
    const ansFh = res?.fhBonusAnswer ?? '–';
    const ansSh = res?.shBonusAnswer ?? '–';

    const fhMatch = res?.fhBonusAnswer && guess?.fhBonus &&
      String(guess.fhBonus).trim().toLowerCase() === String(res.fhBonusAnswer).trim().toLowerCase();
    const shMatch = res?.shBonusAnswer && guess?.shBonus &&
      String(guess.shBonus).trim().toLowerCase() === String(res.shBonusAnswer).trim().toLowerCase();

    // ── Outcome icons ────────────────────────────────────────────────────
    let scoreIcon = '';
    if (pts && guess) {
      if (pts.score > 0)       scoreIcon = '<span class="gs-icon gs-icon-correct">✓</span>';
      else if (pts.result > 0) scoreIcon = '<span class="gs-icon gs-icon-partial">✓</span>';
      else                     scoreIcon = '<span class="gs-icon gs-icon-wrong">✗</span>';
    }
    const fhIcon = ansFh !== '–' && myFh !== '–'
      ? (fhMatch ? '<span class="gs-icon gs-icon-correct">✓</span>' : '<span class="gs-icon gs-icon-wrong">✗</span>')
      : '';
    const shIcon = ansSh !== '–' && mySh !== '–'
      ? (shMatch ? '<span class="gs-icon gs-icon-correct">✓</span>' : '<span class="gs-icon gs-icon-wrong">✗</span>')
      : '';

    lockedContent = `
      <div class="gs-locked-grid">
        <div class="gs-locked-row">
          <span class="gs-locked-key">${t('myGuess')}</span>
          <span class="gs-locked-val">${myScore}${scoreIcon}</span>
        </div>
        <div class="gs-locked-row">
          <span class="gs-locked-key">${t('result')}</span>
          <span class="gs-locked-val">${resScore}</span>
        </div>
        ${fhLabel ? `
        <div class="gs-locked-row">
          <span class="gs-locked-key gs-bonus-mini">${t('firstHalf')}: ${escHtml(fhLabel)}</span>
          <span class="gs-locked-val ${fhMatch ? 'gs-correct' : ''}">
            ${escHtml(String(myFh))}${fhIcon}
            ${ansFh !== '–' ? `<span class="gs-answer-hint">↳ ${escHtml(String(ansFh))}</span>` : ''}
          </span>
        </div>` : ''}
        ${shLabel ? `
        <div class="gs-locked-row">
          <span class="gs-locked-key gs-bonus-mini">${t('secondHalf')}: ${escHtml(shLabel)}</span>
          <span class="gs-locked-val ${shMatch ? 'gs-correct' : ''}">
            ${escHtml(String(mySh))}${shIcon}
            ${ansSh !== '–' ? `<span class="gs-answer-hint">↳ ${escHtml(String(ansSh))}</span>` : ''}
          </span>
        </div>` : ''}
      </div>
      ${pts ? pointsBadge(pts) : ''}`;
  }

  // ── Guess form (upcoming + logged in) ───────────────────────────────────
  let formContent = '';
  if (!isLocked && S.user) {
    const hv = guess?.homeScore ?? '';
    const av = guess?.awayScore ?? '';
    const fhVal = guess?.fhBonus;
    const shVal = guess?.shBonus;
    formContent = `
      <form class="gs-guess-form" data-idx="${idx}">
        <div class="gs-guess-section-label">${t('score')}</div>
        <div class="gs-score-row">
          <div class="gs-team-score">
            <span class="gs-team-name-small">${escHtml(teamName(m.team1))}</span>
            <input type="number" class="gs-score-input" name="homeScore"
                   min="0" max="30" value="${hv}" placeholder="0" />
          </div>
          <span class="gs-score-sep">:</span>
          <div class="gs-team-score">
            <span class="gs-team-name-small">${escHtml(teamName(m.team2))}</span>
            <input type="number" class="gs-score-input" name="awayScore"
                   min="0" max="30" value="${av}" placeholder="0" />
          </div>
        </div>
        ${buildBonusInput(fhBonus, idx, 'fh', fhVal)}
        ${buildBonusInput(shBonus, idx, 'sh', shVal)}
        <button type="submit" class="btn-primary gs-save-btn ${guess ? 'gs-saved' : ''}">
          ${guess ? t('edit') : t('save')}
        </button>
      </form>`;
  } else if (!isLocked && !S.user) {
    formContent = `<div class="gs-no-user-msg">${t('notLoggedIn')}</div>`;
  }

  // ── Admin button ────────────────────────────────────────────────────────
  const adminBtn = (S.user?.isAdmin && (status === 'finished' || status === 'live'))
    ? `<button class="gs-admin-btn" data-admin-idx="${idx}" title="${t('adminPanel')}">⚙</button>`
    : '';

  return `
    <div class="gs-card ${isLocked ? 'gs-card-locked' : ''}" data-group="${escHtml(m.group)}">
      <div class="gs-card-header">
        <div class="gs-card-teams">
          <span class="gs-team1">${escHtml(teamName(m.team1))}</span>
          <span class="gs-vs">vs</span>
          <span class="gs-team2">${escHtml(teamName(m.team2))}</span>
        </div>
        <span class="gs-status-badge ${statusCls}">${statusLabel}</span>
        ${adminBtn}
      </div>
      <div class="gs-card-meta">
        <span class="gs-meta-date">${formatKickoff(m)}</span>
        <span class="gs-meta-ground">📍 ${escHtml(m.ground)}</span>
        <span class="gs-meta-round">${escHtml(m.round)}</span>
      </div>
      <div class="gs-card-body">
        ${isLocked ? lockedContent : formContent}
      </div>
    </div>`;
}

// ── Points calculator (client-side mirror of server logic) ───────────────────
function calcPoints(guess, resultScore, fhAnswer, shAnswer) {
  const pts = { score: 0, result: 0, fhBonus: 0, shBonus: 0, total: 0 };
  if (!guess || !resultScore) return pts;
  const cfg = S.points;
  const { homeScore: gh, awayScore: ga } = guess;
  const { home: rh, away: ra }           = resultScore;
  if ([gh, ga, rh, ra].every(v => v !== null && v !== undefined)) {
    if (gh === rh && ga === ra) {
      pts.score  = cfg.correct_score  ?? 5;
      pts.result = cfg.correct_result ?? 3;
    } else if ((gh > ga && rh > ra) || (gh === ga && rh === ra) || (gh < ga && rh < ra)) {
      pts.result = cfg.correct_result ?? 3;
    }
  }
  const norm = v => String(v ?? '').trim().toLowerCase();
  if (norm(guess.fhBonus) && norm(fhAnswer) && norm(guess.fhBonus) === norm(fhAnswer))
    pts.fhBonus = cfg.correct_fh_bonus ?? 1;
  if (norm(guess.shBonus) && norm(shAnswer) && norm(guess.shBonus) === norm(shAnswer))
    pts.shBonus = cfg.correct_sh_bonus ?? 1;
  pts.total = pts.score + pts.result + pts.fhBonus + pts.shBonus;
  return pts;
}

// ── Render group tabs ─────────────────────────────────────────────────────────
function renderGroupTabs() {
  const container = $('group-tabs');
  if (container) container.innerHTML = '';
}

// ── Render match cards for current group ─────────────────────────────────────
function formatDate(dateStr) {
  try {
    const d = new Date(dateStr + 'T12:00:00Z');
    return new Intl.DateTimeFormat(S.lang === 'tr' ? 'tr-TR' : 'en-GB', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    }).format(d);
  } catch { return dateStr; }
}

function renderCurrentGroup() {
  const container = $('matches-container');
  if (!container) return;
  if (S.matches.length === 0) {
    container.innerHTML = `<div class="gs-empty">${t('noResults')}</div>`;
    return;
  }
  const filtered = S.matches.filter(m => {
    const status = matchStatus(m);
    if (S.matchFilter === 'all') return true;
    return status === S.matchFilter;
  });
  if (filtered.length === 0) {
    container.innerHTML = `<div class="gs-empty">${t('noMatchesForFilter')}</div>`;
    return;
  }
  const sorted = [...filtered].sort((a, b) => {
    const da = a.utcKickoff || `${a.date}T00:00:00Z`;
    const db = b.utcKickoff || `${b.date}T00:00:00Z`;
    return da < db ? -1 : da > db ? 1 : 0;
  });
  const byDate = {};
  for (const m of sorted) {
    const key = m.date || 'Unknown';
    if (!byDate[key]) byDate[key] = [];
    byDate[key].push(m);
  }
  let html = '';
  for (const [date, matches] of Object.entries(byDate)) {
    const cols = Math.min(matches.length, 4);
    html += `<div class="gs-date-header">${formatDate(date)}</div>`;
    html += `<div class="gs-matches-grid cols-${cols}">${matches.map(renderMatchCard).join('')}</div>`;
  }
  container.innerHTML = html;
  container.querySelectorAll('.gs-guess-form').forEach(form => {
    form.addEventListener('submit', handleGuessSubmit);
  });
  container.querySelectorAll('.gs-admin-btn').forEach(btn => {
    btn.addEventListener('click', () => openAdminModal(Number(btn.dataset.adminIdx)));
  });
}

// ── Handle guess submit ───────────────────────────────────────────────────────
async function handleGuessSubmit(e) {
  e.preventDefault();
  const form  = e.currentTarget;
  const idx   = Number(form.dataset.idx);
  const match = S.matches.find(m => m.index === idx);
  if (!match) return;

  const fd = new FormData(form);
  const hs = parseInt(fd.get('homeScore'), 10);
  const as_ = parseInt(fd.get('awayScore'), 10);
  const fhEl = $(`bonus-fh-${idx}`);
  const shEl = $(`bonus-sh-${idx}`);

  if (isNaN(hs) || isNaN(as_)) {
    showToast(t('errorSave'), true);
    return;
  }

  const btn = form.querySelector('.gs-save-btn');
  btn.textContent = t('saving');
  btn.disabled    = true;

  try {
    await POST('/api/groupstage/guess', {
      token:      S.token,
      matchIndex: idx,
      homeScore:  hs,
      awayScore:  as_,
      fhBonus:    fhEl ? fhEl.value.trim() || null : null,
      shBonus:    shEl ? shEl.value.trim() || null : null,
    });
    S.guesses[String(idx)] = {
      homeScore: hs, awayScore: as_,
      fhBonus: fhEl?.value.trim() || null,
      shBonus: shEl?.value.trim() || null,
    };
    showToast(t('savedOk'));
    btn.textContent = t('edit');
    btn.classList.add('gs-saved');
  } catch (err) {
    showToast(err.message || t('errorSave'), true);
    btn.textContent = t('save');
  } finally {
    btn.disabled = false;
  }
}

// ── Leaderboard renderer ──────────────────────────────────────────────────────
function renderLeaderboard() {
  const container = $('leaderboard-container');
  if (!container) return;
  if (S.leaderboard.length === 0) {
    container.innerHTML = `<p class="gs-empty">${t('noResults')}</p>`;
    return;
  }
  const medals = ['🥇', '🥈', '🥉'];
  const rows = S.leaderboard.map((entry, i) => {
    const medal = medals[i] || `${i + 1}.`;
    const logoHtml = buildLogoMarkup(entry.logoData, 'gs-lb-logo', 'gs-lb-logo-default');
    const flagHtml = buildFlagMarkup(entry.supportedTeam, 'gs-lb-flag');
    return `
      <tr class="${S.user?.username === entry.username ? 'gs-lb-me' : ''}">
        <td class="gs-lb-rank">${medal}</td>
        <td class="gs-lb-name">
          <span class="gs-lb-user">
            ${logoHtml}
            <span>${escHtml(entry.displayName)}</span>
            ${flagHtml}
          </span>
        </td>
        <td class="gs-lb-pts">${entry.totalPoints}</td>
      </tr>`;
  }).join('');
  container.innerHTML = `
    <table class="gs-lb-table">
      <thead>
        <tr>
          <th>${t('rank')}</th>
          <th>${t('player')}</th>
          <th>${t('points')}</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ── Submitted guesses renderer ─────────────────────────────────────────────
function renderSubmittedGuesses() {
  const container = $('guesses-container');
  if (!container) return;

  const entries = S.allGuesses || {};
  const keys = Object.keys(entries);
  if (keys.length === 0) {
    container.innerHTML = `<div class="gs-guess-empty">${t('noStartedMatches')}</div>`;
    return;
  }

  const matchMap = new Map(S.matches.map(m => [String(m.index), m]));
  const sorted = keys
    .map(k => ({ key: k, match: matchMap.get(k) }))
    .filter(x => x.match)
    .sort((a, b) => {
      const da = a.match.utcKickoff || `${a.match.date}T00:00:00Z`;
      const db = b.match.utcKickoff || `${b.match.date}T00:00:00Z`;
      return da < db ? 1 : da > db ? -1 : 0;
    });

  const cards = sorted.map(({ key, match }) => {
    const entry = entries[key] || {};
    const result = entry.result;
    const fhAns = entry.fhBonusAnswer;
    const shAns = entry.shBonusAnswer;
    const fhAnsLabel = fhAns ? escHtml(String(fhAns)) : '–';
    const shAnsLabel = shAns ? escHtml(String(shAns)) : '–';
    const guesses = entry.guesses || [];
    const resultLabel = result ? `${result.home} – ${result.away}` : '';
    const statusLabel = t(entry.status || matchStatus(match));

    const rows = guesses.length
      ? guesses.map(g => {
          const pts = g.points;
          let icon = '';
          if (result) {
            if (pts && pts.score > 0) icon = '<span class="gs-icon gs-icon-correct">✓</span>';
            else if (pts && pts.result > 0) icon = '<span class="gs-icon gs-icon-partial">✓</span>';
            else icon = '<span class="gs-icon gs-icon-wrong">✗</span>';
          }
          const ptsClass = pts
            ? (pts.total <= 0 ? 'gs-pts-red' : pts.total <= 3 ? 'gs-pts-yellow' : 'gs-pts-green')
            : '';
          const ptsHtml = pts
            ? `<span class="gs-guess-points ${ptsClass}">+${pts.total} ${t('points')}</span>`
            : '';
          const norm = v => String(v ?? '').trim().toLowerCase();
          const fhMatch = fhAns && g.fhBonus && norm(g.fhBonus) === norm(fhAns);
          const shMatch = shAns && g.shBonus && norm(g.shBonus) === norm(shAns);
          const fhIcon = fhAns && g.fhBonus
            ? (fhMatch ? '<span class="gs-icon gs-icon-correct">✓</span>' : '<span class="gs-icon gs-icon-wrong">✗</span>')
            : '';
          const shIcon = shAns && g.shBonus
            ? (shMatch ? '<span class="gs-icon gs-icon-correct">✓</span>' : '<span class="gs-icon gs-icon-wrong">✗</span>')
            : '';
          const scoreLabel = `${g.homeScore} – ${g.awayScore}${icon}`;
          const fhLabel = g.fhBonus ? `${t('firstHalf')}: ${escHtml(String(g.fhBonus))}${fhIcon}` : '';
          const shLabel = g.shBonus ? `${t('secondHalf')}: ${escHtml(String(g.shBonus))}${shIcon}` : '';
          const logoHtml = buildLogoMarkup(g.logoData, 'gs-lb-logo', 'gs-lb-logo-default');
          const flagHtml = buildFlagMarkup(g.supportedTeam, 'gs-lb-flag');
          const bonusHtml = `<div class="gs-guess-bonuses">
                <span class="gs-guess-bonus">${scoreLabel}</span>
                ${fhLabel ? `<span class="gs-guess-bonus">${fhLabel}</span>` : ''}
                ${shLabel ? `<span class="gs-guess-bonus">${shLabel}</span>` : ''}
              </div>`;
          return `
            <div class="gs-guess-row">
              <div class="gs-guess-user">
                <span class="gs-lb-user">
                  ${logoHtml}
                  <span class="gs-guess-name">${escHtml(g.displayName || g.username)}</span>
                  ${flagHtml}
                </span>
                ${bonusHtml}
              </div>
              ${ptsHtml}
            </div>`;
        }).join('')
      : `<div class="gs-guess-empty">${t('noGuesses')}</div>`;

    return `
      <div class="gs-guess-card">
        <div class="gs-guess-card-header">
          <div class="gs-guess-card-title">${escHtml(teamName(match.team1))} vs ${escHtml(teamName(match.team2))}</div>
          <div class="gs-guess-result">${result
            ? `${t('result')}: <strong>${resultLabel}</strong> · ${t('firstHalf')}: <strong>${fhAnsLabel}</strong> · ${t('secondHalf')}: <strong>${shAnsLabel}</strong>`
            : `${statusLabel}: ${formatKickoff(match)}`}</div>
        </div>
        <div class="gs-guess-rows">${rows}</div>
      </div>`;
  }).join('');

  container.innerHTML = cards || `<div class="gs-guess-empty">${t('noStartedMatches')}</div>`;
}

// ── Login CTA (visible when not logged in) ────────────────────────────────────
function renderLoginCTA() {
  const cta = $('login-cta');
  if (!cta) return;
  if (S.user) {
    cta.classList.add('hidden');
  } else {
    cta.classList.remove('hidden');
    cta.querySelector('[data-i18n]').textContent = t('notLoggedIn');
    cta.querySelector('button').textContent      = t('login');
  }
}

// ── User pill (header) ────────────────────────────────────────────────────────
function renderUserPill() {
  const pill = $('user-pill');
  if (!pill) return;
  if (S.user) {
    const logoHtml = buildLogoMarkup(S.user.logoData, 'gs-user-logo', 'gs-user-logo-default');
    const flagHtml = buildFlagMarkup(S.user.supportedTeam, 'gs-user-flag');
    pill.innerHTML = `
      <div id="btn-open-profile" class="gs-pill-profile-trigger" role="button" tabindex="0" aria-label="${escHtml(t('editProfile'))}">
        ${logoHtml}
        <span class="gs-pill-name">${escHtml(S.user.displayName)}</span>
        ${flagHtml}
        ${S.user.isAdmin ? '<span class="gs-pill-admin">ADMIN</span>' : ''}
      </div>
      <button id="btn-logout" class="btn-ghost">${t('logout')}</button>`;
    pill.classList.remove('hidden');
    $('btn-logout').addEventListener('click', doLogout);
    const openProfile = () => showProfileModal();
    $('btn-open-profile').addEventListener('click', openProfile);
    $('btn-open-profile').addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openProfile();
      }
    });
  } else {
    pill.innerHTML = `<button id="btn-open-auth-hdr" class="btn-secondary">${t('login')} / ${t('register')}</button>`;
    pill.classList.remove('hidden');
    $('btn-open-auth-hdr').addEventListener('click', showAuthModal);
  }
}

async function doProfileUpdate(e) {
  e.preventDefault();
  $('profile-error').classList.add('hidden');
  try {
    const currentPassword = $('profile-current-password').value;
    const newPassword     = $('profile-new-password').value;
    const supportedTeam   = $('profile-team')?.value || '';
    const logoInput       = $('profile-logo');
    let logoData = null;
    if (logoInput && logoInput.files && logoInput.files[0]) {
      const file = logoInput.files[0];
      if (file.size > LOGO_MAX_BYTES) {
        throw new Error(t('logoTooLarge'));
      }
      logoData = await readLogoFile(file);
    }

    const r = await POST('/api/auth/profile', {
      token: S.token,
      currentPassword,
      newPassword,
      supportedTeam,
      logoData,
    });

    if (r.token && r.token !== S.token) {
      S.token = r.token;
      localStorage.setItem('gs_token', r.token);
    }
    S.user = {
      username: r.username,
      displayName: r.displayName,
      isAdmin: r.isAdmin,
      supportedTeam: r.supportedTeam || null,
      logoData: r.logoData || null,
    };
    hideProfileModal();
    renderUserPill();
    renderLoginCTA();
    showToast(t('profileSaved'));
  } catch (err) {
    const msg = err.message === 'Incorrect current password'
      ? t('currentPasswordFail')
      : (err.message || t('profileFail'));
    $('profile-error').textContent = msg;
    $('profile-error').classList.remove('hidden');
  }
}

// ── Admin modal ───────────────────────────────────────────────────────────────
function openAdminModal(idx) {
  const m = S.matches.find(x => x.index === idx);
  if (!m) return;
  S.adminMatchIdx = idx;
  $('admin-match-index').value = idx;
  $('admin-match-title').textContent = `${teamName(m.team1)} vs ${teamName(m.team2)} – ${m.date}`;
  $('admin-team1-label').textContent  = teamName(m.team1);
  $('admin-team2-label').textContent  = teamName(m.team2);
  const res = S.results[String(idx)];
  $('admin-home-score').value = res?.score?.home ?? 0;
  $('admin-away-score').value = res?.score?.away ?? 0;
  const fhLabel = m.firstHalfBonus  ? (S.lang === 'tr' ? m.firstHalfBonus.tr  : m.firstHalfBonus.en)  : t('fhBonusAnswer');
  const shLabel = m.secondHalfBonus ? (S.lang === 'tr' ? m.secondHalfBonus.tr : m.secondHalfBonus.en) : t('shBonusAnswer');
  $('admin-fh-label').textContent = fhLabel;
  $('admin-sh-label').textContent = shLabel;
  $('admin-fh-answer').value = res?.fhBonusAnswer ?? '';
  $('admin-sh-answer').value = res?.shBonusAnswer ?? '';
  $('admin-error').classList.add('hidden');
  $('admin-modal').classList.remove('hidden');
}

async function handleAdminSubmit(e) {
  e.preventDefault();
  const idx = parseInt($('admin-match-index').value, 10);
  $('admin-error').classList.add('hidden');
  try {
    const r = await POST('/api/groupstage/result', {
      token:         S.token,
      matchIndex:    idx,
      homeScore:     parseInt($('admin-home-score').value, 10),
      awayScore:     parseInt($('admin-away-score').value, 10),
      fhBonusAnswer: $('admin-fh-answer').value.trim() || null,
      shBonusAnswer: $('admin-sh-answer').value.trim() || null,
    });
    S.leaderboard = r.leaderboard || S.leaderboard;
    // Refresh results
    const rR = await GET(`/api/groupstage/results?token=${S.token}`);
    S.results = rR.results || {};
    showToast(t('savedOk'));
    $('admin-modal').classList.add('hidden');
    renderCurrentGroup();
    if ($('tab-leaderboard').classList.contains('gs-tab-content') &&
        !$('tab-leaderboard').classList.contains('hidden')) {
      renderLeaderboard();
    }
  } catch (err) {
    $('admin-error').textContent = err.message;
    $('admin-error').classList.remove('hidden');
  }
}

async function handleFetchFromAPI() {
  const idx = parseInt($('admin-match-index').value, 10);
  $('admin-error').classList.add('hidden');
  try {
    const r = await POST('/api/groupstage/score', { token: S.token, matchIndex: idx });
    if (r.result) {
      $('admin-home-score').value = r.result.home;
      $('admin-away-score').value = r.result.away;
    }
    showToast(t('fetchOk'));
  } catch (err) {
    $('admin-error').textContent = err.message || t('fetchFail');
    $('admin-error').classList.remove('hidden');
  }
}

// ── Tab switching ─────────────────────────────────────────────────────────────
function switchMainTab(name) {
  document.querySelectorAll('.gs-main-tabs .gs-tab').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === name);
  });
  $('tab-predictions').classList.toggle('hidden', name !== 'predictions');
  $('tab-guesses').classList.toggle('hidden', name !== 'guesses');
  $('tab-leaderboard').classList.toggle('hidden', name !== 'leaderboard');
  $('predictions-filter-panel').classList.toggle('hidden', name !== 'predictions');
  if (name === 'leaderboard') {
    loadLeaderboard().then(renderLeaderboard);
  }
  if (name === 'guesses') {
    loadAllGuesses().then(renderSubmittedGuesses);
  }
}

// ── Initialisation ────────────────────────────────────────────────────────────
async function init() {
  // Lang
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      S.lang = btn.dataset.lang;
      localStorage.setItem('gs_lang', S.lang);
      applyLang();
      populateTeamSelect();
      populateTeamSelect('profile-team', $('profile-team')?.value || (S.user?.supportedTeam || ''));
      renderGroupTabs();
      renderCurrentGroup();
      renderUserPill();
      renderLoginCTA();
    });
  });
  applyLang();

  // Auth modal triggers
  $('tab-login').addEventListener('click', () => {
    $('login-form').classList.remove('hidden');
    $('register-form').classList.add('hidden');
    $('tab-login').classList.add('active');
    $('tab-register').classList.remove('active');
  });
  $('tab-register').addEventListener('click', () => {
    $('login-form').classList.add('hidden');
    $('register-form').classList.remove('hidden');
    $('tab-register').classList.add('active');
    $('tab-login').classList.remove('active');
  });
  $('auth-modal').addEventListener('click', e => {
    if (e.target === $('auth-modal')) hideAuthModal();
  });
  $('login-form').addEventListener('submit', doLogin);
  $('register-form').addEventListener('submit', doRegister);

  $('profile-modal').addEventListener('click', e => {
    if (e.target === $('profile-modal')) hideProfileModal();
  });
  $('profile-modal-close').addEventListener('click', hideProfileModal);
  $('profile-cancel').addEventListener('click', hideProfileModal);
  $('profile-form').addEventListener('submit', doProfileUpdate);

  // Open auth from login-cta / btn-open-auth
  document.addEventListener('click', e => {
    if (e.target.id === 'btn-open-auth') showAuthModal();
  });

  // Main tab switching
  document.querySelectorAll('.gs-main-tabs .gs-tab').forEach(btn => {
    btn.addEventListener('click', () => switchMainTab(btn.dataset.tab));
  });

  // Prediction status filters
  document.querySelectorAll('.gs-status-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.gs-status-filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      S.matchFilter = btn.dataset.matchFilter || 'all';
      renderCurrentGroup();
    });
  });

  // Admin modal
  $('admin-modal').addEventListener('click', e => {
    if (e.target === $('admin-modal')) $('admin-modal').classList.add('hidden');
  });
  $('admin-modal-close').addEventListener('click', () => $('admin-modal').classList.add('hidden'));
  $('admin-result-form').addEventListener('submit', handleAdminSubmit);
  $('btn-fetch-api').addEventListener('click', handleFetchFromAPI);

  // Load data
  _acSetup();
  await Promise.all([checkAuth(), loadMatches(), loadSquads(), loadVisitorContext()]);
  populateTeamSelect();
  populateTeamSelect('profile-team', S.user?.supportedTeam || '');
  if (S.user) await loadUserData();

  // Show app
  $('app').classList.remove('hidden');
  renderUserPill();
  renderLoginCTA();
  updateStickyOffsets();

  renderGroupTabs();
  renderCurrentGroup();

  if (!$('tab-guesses').classList.contains('hidden')) {
    await loadAllGuesses();
    renderSubmittedGuesses();
  }

  // Auto-refresh live match statuses every 60s
  setInterval(() => {
    const hasLive = S.matches.some(m => matchStatus(m) === 'live');
    if (hasLive) {
      loadUserData().then(renderCurrentGroup);
      if (!$('tab-guesses').classList.contains('hidden')) {
        loadAllGuesses().then(renderSubmittedGuesses);
      }
    }
  }, 60_000);

  window.addEventListener('resize', updateStickyOffsets, { passive: true });
  window.addEventListener('orientationchange', updateStickyOffsets, { passive: true });
  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => updateStickyOffsets());
    const header = document.querySelector('header');
    const controls = document.querySelector('.gs-controls');
    if (header) ro.observe(header);
    if (controls) ro.observe(controls);
  }
}

document.addEventListener('DOMContentLoaded', init);
