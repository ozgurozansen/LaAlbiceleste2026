#!/usr/bin/env python3
"""
LaAlbiceleste2026 API — pure Python stdlib server
Usage: python3 server.py [port]   (default port 3000)
"""

import base64
import http.client
import ipaddress
import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.parse
import threading
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import re
import unicodedata
import uuid
import random
from datetime import datetime, timezone, timedelta

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8000"))
BULLETIN_URL = "https://bulten.nesine.com/api/bulten/getprebultenfull"
CACHE_TTL = 60  # seconds
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
DATA_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
LOGO_MAX_BYTES = 2 * 1024 * 1024
ASSET_VERSION = "20260610-1"


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"defaults": {"sport": 1, "leagues": []}, "sports": [], "leagues": []}


CONFIG = load_config()
LEAGUE_NAMES      = {entry["code"]: entry["name"] for entry in CONFIG.get("leagues", [])}
SPORT_TYPES       = {int(k): v for k, v in CONFIG.get("sport_types", {}).items()}
MARKET_TYPE_NAMES    = {int(k): v for k, v in CONFIG.get("market_type_names", {}).items()}
MARKET_TYPE_NAMES_TR = {int(k): v for k, v in CONFIG.get("market_type_names_tr", {}).items()}
_OU_MTIDS         = frozenset(CONFIG.get("ou_mtids", []))
_AH_MTIDS         = frozenset(CONFIG.get("ah_mtids", []))
_EH_MTIDS         = frozenset(CONFIG.get("eh_mtids", []))
# Markets hidden from the betting page (unsettleable or wrong-sport)
# Maç Özel group: 187, 189, 190, 716, 804
# Unsettleable football markets: 715, 744, 763, 764, 871, 872, 873, 874
_KO_HIDDEN_TYPEIDS = frozenset({
    187, 189, 190, 716, 804,
    715, 744, 763, 764,
    871, 872, 873, 874,
})
OUTCOME_LABELS    = {int(k): {int(n): v for n, v in oc.items()}
                     for k, oc in CONFIG.get("outcome_labels", {}).items()}
OUTCOME_LABELS_TR = {int(k): {int(n): v for n, v in oc.items()}
                     for k, oc in CONFIG.get("outcome_labels_tr", {}).items()}
SPORT_TYPES_TR    = {int(k): v for k, v in CONFIG.get("sport_types_tr", {}).items()}
_TR_TO_EN         = CONFIG.get("tr_to_en", {})
_TEAM_NAMES_EN    = {k.lower(): v for k, v in CONFIG.get("team_names_en", {}).items()}

def _team_en(tr_name):
    return _TEAM_NAMES_EN.get((tr_name or "").lower(), tr_name or "")

def _match_name_en(minfo, fallback=""):
    """Return the English match name, always translating both team parts through _team_en.
    This handles partially-translated nameEn values (e.g. 'Curaçao vs Fildişi Sahili')."""
    name = minfo.get("nameEn") or minfo.get("name") or fallback
    if " vs " in name:
        parts = name.split(" vs ", 1)
        return f"{_team_en(parts[0])} vs {_team_en(parts[1])}"
    return name

# ── Group-stage data paths ────────────────────────────────────────────────────
_GS_FILE    = os.path.join(DATA_DIR, "groupstage2026.json")
_BFH_FILE   = os.path.join(DATA_DIR, "bonusfirsthalf.txt")
_BSH_FILE   = os.path.join(DATA_DIR, "bonussecondhalf.txt")
_SQUAD_FILE = os.path.join(DATA_DIR, "squad.json")
_USERS_FILE = os.path.join(DATA_DIR, "users.json")
_GUESS_FILE = os.path.join(DATA_DIR, "guesses.json")
_RES_FILE   = os.path.join(DATA_DIR, "match_results.json")
_BONUS_ASSIGN_FILE = os.path.join(DATA_DIR, "bonus_assignments.json")
_KO_BETS_FILE      = os.path.join(DATA_DIR, "knockout_bets.json")
_KO_MATCH_LOG_FILE = os.path.join(DATA_DIR, "knockout_match_log.json")
_KO_RESULTS_FILE   = os.path.join(DATA_DIR, "knockout_results.json")

KNOCKOUT_CREDIT_BASE  = 100
KNOCKOUT_MIN_BET      = 1
KNOCKOUT_MAX_BET      = 8
KNOCKOUT_NO_BET_PENALTY = 5

POINTS_CFG  = CONFIG.get("points", {"correct_score": 5, "correct_result": 3,
                                     "correct_fh_bonus": 1, "correct_sh_bonus": 1})
STAGE_REDIRECT_CFG = CONFIG.get("stage_redirect", {})


def _clean_stage_path(path, fallback):
    val = str(path or "").strip()
    if not val:
        return fallback
    if not val.startswith("/"):
        val = "/" + val
    return val


_GROUP_STAGE_PATH = _clean_stage_path(
    STAGE_REDIRECT_CFG.get("group_stage_path", "/groupstage.html"),
    "/groupstage.html",
)
_KNOCKOUT_STAGE_PATH = _clean_stage_path(
    STAGE_REDIRECT_CFG.get("knockout_stage_path", "/knockout.html"),
    "/knockout.html",
)


def _load_bonus_file(path):
    items = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                m = re.match(r'^(.+?)\s*\((.+)\)\s*$', line)
                tr_text = m.group(1).strip() if m else line
                en_text = m.group(2).strip() if m else line
                input_type = "player" if "kim" in tr_text.lower() else "minute"
                items.append({"tr": tr_text, "en": en_text, "inputType": input_type})
    except FileNotFoundError:
        pass
    return items


def _build_bonus_schedule(items, match_count):
    if not items or match_count <= 0:
        return []
    repeats, remainder = divmod(match_count, len(items))
    pool = list(items) * repeats + list(items[:remainder])
    random.SystemRandom().shuffle(pool)
    return pool


def _load_or_create_bonus_assignments(fh_items, sh_items, match_count):
    if match_count <= 0:
        return [], []

    try:
        with open(_BONUS_ASSIGN_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
        fh_sched = existing.get("fhSchedule") or []
        sh_sched = existing.get("shSchedule") or []
        if len(fh_sched) == match_count and len(sh_sched) == match_count:
            return fh_sched, sh_sched
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    fh_sched = _build_bonus_schedule(fh_items, match_count)
    sh_sched = _build_bonus_schedule(sh_items, match_count)
    os.makedirs(os.path.dirname(_BONUS_ASSIGN_FILE), exist_ok=True)
    snapshot = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "matchCount": match_count,
        "fhSchedule": fh_sched,
        "shSchedule": sh_sched,
    }
    with open(_BONUS_ASSIGN_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    return fh_sched, sh_sched


_BONUS_FH = _load_bonus_file(_BFH_FILE)
_BONUS_SH = _load_bonus_file(_BSH_FILE)


def _load_all_matches():
    try:
        with open(_GS_FILE, encoding="utf-8") as f:
            return json.load(f).get("matches", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _load_squad_data():
    try:
        with open(_SQUAD_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _build_squad_lookup(squad):
    lookup = {}
    for grp in squad.get("groups", []):
        for team in grp.get("teams", []):
            name = team.get("team", "")
            lookup[name] = [
                {"name": p["name"], "position": p.get("position", ""),
                 "number": p.get("jersey_number")}
                for p in team.get("players", [])
            ]
    return lookup


_ALL_MATCHES   = _load_all_matches()
_SQUAD_LOOKUP  = _build_squad_lookup(_load_squad_data())
_GROUP_MATCHES = [m for m in _ALL_MATCHES if "group" in m]
_BONUS_FH_SCHEDULE, _BONUS_SH_SCHEDULE = _load_or_create_bonus_assignments(
    _BONUS_FH,
    _BONUS_SH,
    len(_GROUP_MATCHES),
)
_data_lock     = threading.Lock()
_tokens        = {}   # token -> {username, expires}
_SUPPORTED_TEAMS = sorted({
    t
    for m in _ALL_MATCHES
    if "group" in m
    for t in (m.get("team1"), m.get("team2"))
    if t
})


# ── Time helpers ──────────────────────────────────────────────────────────────
def _parse_kickoff_utc(date_str, time_str):
    m = re.match(r'(\d+):(\d+)\s*UTC([+-]\d+(?:\.\d+)?)', time_str or "")
    if not m:
        return None
    h, mn, off = int(m.group(1)), int(m.group(2)), float(m.group(3))
    try:
        dt = datetime.strptime(f"{date_str} {h:02d}:{mn:02d}", "%Y-%m-%d %H:%M")
        dt = dt - timedelta(hours=off)
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _match_status(ko_utc):
    if ko_utc is None:
        return "upcoming"
    now = datetime.now(timezone.utc)
    if now < ko_utc:
        return "upcoming"
    if now < ko_utc + timedelta(hours=2, minutes=30):
        return "live"
    return "finished"


def _is_group_stage_finished():
    group_matches = [m for m in _ALL_MATCHES if "group" in m]
    if not group_matches:
        return False
    kickoffs = [
        _parse_kickoff_utc(m.get("date", ""), m.get("time", ""))
        for m in group_matches
    ]
    kickoffs = [ko for ko in kickoffs if ko is not None]
    if not kickoffs:
        return False

    last_group_kickoff = max(kickoffs)
    group_stage_end = last_group_kickoff + timedelta(hours=9)
    return datetime.now(timezone.utc) >= group_stage_end


def _active_stage_name():
    force_stage = str(STAGE_REDIRECT_CFG.get("force_stage", "")).strip().lower()
    if force_stage in ("group", "knockout"):
        return force_stage
    return "knockout" if _is_group_stage_finished() else "group"


def _active_stage_target():
    return _KNOCKOUT_STAGE_PATH if _active_stage_name() == "knockout" else _GROUP_STAGE_PATH


def _enrich_match(idx, m, bonus_idx=None):
    if bonus_idx is None:
        bonus_idx = idx
    fhb  = _BONUS_FH_SCHEDULE[bonus_idx] if bonus_idx < len(_BONUS_FH_SCHEDULE) else None
    shb  = _BONUS_SH_SCHEDULE[bonus_idx] if bonus_idx < len(_BONUS_SH_SCHEDULE) else None
    ko   = _parse_kickoff_utc(m.get("date", ""), m.get("time", ""))
    return {
        **m,
        "index":          idx,
        "isGroupStage":   "group" in m,
        "utcKickoff":     ko.isoformat() if ko else None,
        "status":         _match_status(ko),
        "firstHalfBonus": fhb,
        "secondHalfBonus": shb,
    }


# ── Auth helpers ──────────────────────────────────────────────────────────────
def _hash_pw(pw):
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def _create_token(username):
    token = str(uuid.uuid4())
    exp   = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    with _data_lock:
        _tokens[token] = {"username": username, "expires": exp}
    return token


def _validate_token(token):
    if not token:
        return None
    with _data_lock:
        t = _tokens.get(token)
    if not t:
        return None
    if datetime.now(timezone.utc) > datetime.fromisoformat(t["expires"]):
        with _data_lock:
            _tokens.pop(token, None)
        return None
    return t["username"]


def _invalidate_user_tokens(username):
    with _data_lock:
        for token, info in list(_tokens.items()):
            if info.get("username") == username:
                _tokens.pop(token, None)


def _validate_logo_data(logo_data):
    if not logo_data:
        return None
    if not isinstance(logo_data, str) or not logo_data.startswith("data:image/"):
        raise ValueError("Invalid logo data")
    try:
        _, encoded_logo = logo_data.split(",", 1)
        decoded_logo = base64.b64decode(encoded_logo, validate=True)
    except (ValueError, TypeError, base64.binascii.Error):
        raise ValueError("Invalid logo data")
    if len(decoded_logo) > LOGO_MAX_BYTES:
        raise OverflowError("Logo is too large")
    return logo_data


# ── JSON file helpers ─────────────────────────────────────────────────────────
def _jload(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _jsave(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _is_admin(username):
    users = _jload(_USERS_FILE, {"users": {}})
    return users.get("users", {}).get(username, {}).get("isAdmin", False)


# ── Knockout betting helpers ───────────────────────────────────────────────────
def _ko_update_match_log(matches):
    """Persist new knockout match IDs to the match log for credit penalty tracking."""
    with _data_lock:
        log = _jload(_KO_MATCH_LOG_FILE, {"matches": {}})
        changed = False
        for m in matches:
            mid = str(m.get("id") or "")
            if not mid:
                continue
            if mid not in log["matches"]:
                ht, at = m.get('homeTeam', ''), m.get('awayTeam', '')
                log["matches"][mid] = {
                    "name":           f"{ht} vs {at}",
                    "nameEn":         f"{_team_en(ht)} vs {_team_en(at)}",
                    "startTimestamp": m.get("startTimestamp"),
                    "firstSeenAt":    datetime.now(timezone.utc).isoformat(),
                }
                changed = True
        if changed:
            _jsave(_KO_MATCH_LOG_FILE, log)


def _ko_compute_credit(username, count_pending=True):
    """Compute current knockout betting credit.

    credit = base - sum(placed bet amounts) - penalty for each started match with no bet
    base = koStartingCredit from users.json if set (exported from group stage), else KNOCKOUT_CREDIT_BASE

    count_pending: when False, bets on matches that haven't started yet are excluded from
    the spent total. Used by the public leaderboard so a user's pending bet (and its amount)
    isn't revealed to other users before kickoff; personal-balance call sites keep the default.
    """
    now_ts = time.time()
    log   = _jload(_KO_MATCH_LOG_FILE, {"matches": {}})
    bets  = _jload(_KO_BETS_FILE, {"bets": {}}).get("bets", {}).get(username, {})
    users = _jload(_USERS_FILE, {"users": {}})
    base  = users.get("users", {}).get(username, {}).get("koStartingCredit", KNOCKOUT_CREDIT_BASE)

    def _has_started(b):
        ts = b.get("startTimestamp")
        if ts is None:
            return True
        try:
            ts_f = float(ts)
            ts_sec = ts_f / 1000.0 if ts_f > 1e10 else ts_f
        except (ValueError, TypeError):
            return True
        return now_ts >= ts_sec

    spent = sum(
        float(b.get("amount", KNOCKOUT_MIN_BET))
        for b in bets.values()
        if count_pending or _has_started(b)
    )
    winnings = sum(float(b.get("payout", 0)) for b in bets.values() if b.get("won") is True)

    penalties = 0
    for mid, minfo in log["matches"].items():
        ts = minfo.get("startTimestamp")
        if not ts:
            continue
        try:
            ts_f = float(ts)
            ts_sec = ts_f / 1000.0 if ts_f > 1e10 else ts_f
        except (ValueError, TypeError):
            continue
        if now_ts >= ts_sec and mid not in bets:
            penalties += KNOCKOUT_NO_BET_PENALTY

    return base - spent - penalties + winnings


# ── Knockout result fetching & settlement ─────────────────────────────────────

def _parse_label_threshold(label):
    """Parse 'Name N+' or 'Name N-' labels into (name_part, threshold, is_over).
    Returns (label, None, None) if no numeric threshold token found."""
    parts = (label or "").strip().rsplit(None, 1)
    if len(parts) == 2:
        m = re.match(r'^(\d+)(\+|-)$', parts[1])
        if m:
            thr = int(m.group(1))
            is_over = m.group(2) == '+'
            return parts[0].strip(), thr, is_over
    return label, None, None


def _ko_find_player(players_dict, name_query):
    """Best-effort fuzzy match a player name against the players dict (keyed by lowercase name)."""
    if not name_query or not players_dict:
        return None
    def _n(s):
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()
    q = _n(name_query)
    norm_map = {_n(k): v for k, v in players_dict.items()}
    if q in norm_map:
        return norm_map[q]
    q_parts = q.split()
    if q_parts:
        for nk, pdata in norm_map.items():
            p_parts = nk.split()
            if p_parts and q_parts[-1] == p_parts[-1]:
                return pdata
    for nk, pdata in norm_map.items():
        if q in nk or nk in q:
            return pdata
    return None


def _ko_settle_bet(bet, result):
    """Return True (won), False (lost), or None (can't determine)."""
    tid  = int(bet.get("typeId") or 0)
    sov  = float(bet.get("spreadValue") or 0)
    n    = int(bet.get("outcomeN") or 0)
    h    = result.get("homeGoals")
    a    = result.get("awayGoals")
    ht_h = result.get("htHomeGoals")
    ht_a = result.get("htAwayGoals")
    pen_h = result.get("penHome")
    pen_a = result.get("penAway")

    # When typeId=0 (Nesine bulletin omitted MTID), infer market type from stored labels
    if not tid and n:
        import re as _re
        mname = (bet.get("marketNameEn") or bet.get("marketName") or "").lower()
        label = (bet.get("outcomeLabelEn") or bet.get("outcomeLabel") or "")
        # Over/Under total goals: "Alt/Üst" or "Over/Under" (not home/away/half variants)
        if ("over/under" in mname or "alt/üst" in mname) and not any(
            x in mname for x in ["home", "away", "1st half", "half", "deplasman", "ev sahibi", "btts", "karşılıklı"]
        ):
            m = _re.search(r'(?:over|under|üst|alt)\s+(\d+\.?\d*)', label, _re.IGNORECASE)
            if m:
                sov = float(m.group(1))
                tid = 12
        # European handicap: "Handikaplı Maç Sonucu" or "Handicap Match Result"
        elif "handikap" in mname or "handicap" in mname:
            m = _re.search(r'\(([-+]?\d+\.?\d*)\)', label)
            if m:
                sov = float(m.group(1))
                tid = 268
        # Result + BTTS combo: "Maç Sonucu ve Karşılıklı Gol" or "Match Result and BTTS"
        elif "match result and" in mname or "sonucu ve karşılıklı" in mname:
            tid = 414
        # Plain BTTS: "Karşılıklı Gol" or "Both Teams to Score"
        elif "karşılıklı gol" in mname or "both teams to score" in mname or "btts" in mname:
            tid = 38

    if h is None or a is None or not tid or not n:
        return None

    def _fr(home, away):
        if home > away: return 1
        if home < away: return 2
        return 0

    fr   = _fr(h, a)
    tot  = h + a

    if tid in (1, 183):   # 1X2 / 1X2 Set Odds
        return {1: fr == 1, 2: fr == 0, 3: fr == 2}.get(n)

    if tid == 3:   # Double Chance: n=1→1X, n=2→12, n=3→X2
        return {1: fr in (1, 0), 2: fr in (1, 2), 3: fr in (0, 2)}.get(n)

    if tid == 38:  # BTTS: n=1→Yes, n=2→No
        scored = h > 0 and a > 0
        return {1: scored, 2: not scored}.get(n)

    if tid == 49:  # Odd/Even total goals: n=1→Odd, n=2→Even
        return {1: tot % 2 == 1, 2: tot % 2 == 0}.get(n)

    if tid == 48:  # Most Goals Half: n=1→1st, n=2→Equal, n=3→2nd
        if ht_h is None or ht_a is None: return None
        h1, h2 = ht_h + ht_a, (h - ht_h) + (a - ht_a)
        return {1: h1 > h2, 2: h1 == h2, 3: h2 > h1}.get(n)

    if tid == 43:  # Total Goals Range: n=1→0-1, n=2→2-3, n=3→4-5, n=4→6+
        return {1: tot <= 1, 2: 2 <= tot <= 3, 3: 4 <= tot <= 5, 4: tot >= 6}.get(n)

    if tid == 588:  # Win Margin / Galibiyet Farkı
        diff = abs(h - a)
        if fr == 0: return {7: True}.get(n, False)  # Draw=7
        elif fr == 1:  # Home win
            return {1: diff >= 3, 2: diff == 2, 3: diff == 1}.get(n, False)
        else:  # Away win
            return {4: diff == 1, 5: diff == 2, 6: diff >= 3}.get(n, False)

    if tid in (11, 12, 13, 810, 812) and sov:   # O/U total goals
        if n == 1: return tot < sov
        if n == 2: return tot > sov
        return None  # push

    if tid in (20, 212, 326, 455, 161) and sov:   # O/U home goals
        if n == 1: return h < sov
        if n == 2: return h > sov
        return None

    if tid in (15, 29, 164, 207, 256, 327, 328, 329, 604) and sov:   # O/U away goals (29=Deplasman Alt/Üst)
        if n == 1: return a < sov
        if n == 2: return a > sov
        return None

    if tid in (268, 100, 101, 185, 791, 884, 887):   # European/standard handicap
        adj = h + sov
        afr = _fr(adj, a)
        return {1: afr == 1, 2: afr == 0, 3: afr == 2}.get(n)

    if tid == 418 and sov:   # Asian Handicap (goals): n=1→Home, n=2→Away
        adj = h + sov
        if adj > a: return {1: True,  2: False}.get(n)
        if adj < a: return {1: False, 2: True}.get(n)
        return None  # push on exact line

    if tid == 182:  # Who Advances: n=1→Home, n=2→Away
        agg_h = result.get("aggHomeGoals")
        agg_a = result.get("aggAwayGoals")
        afr = _fr(agg_h, agg_a) if agg_h is not None and agg_a is not None else fr
        if afr != 0: return {1: afr == 1, 2: afr == 2}.get(n)
        if pen_h is not None and pen_a is not None:
            winner = 1 if pen_h > pen_a else 2
            return {1: winner == 1, 2: winner == 2}.get(n)
        return None  # draw but no penalty data

    if tid == 593:  # Penalty shootout in this match: n=1→Yes, n=2→No
        status = result.get("status", "FT")
        had_pen = status == "PEN"
        return {1: had_pen, 2: not had_pen}.get(n)

    if tid in (432, 434, 450) and ht_h is not None:  # 1st half Odd/Even
        ht_tot = ht_h + (ht_a or 0)
        return {1: ht_tot % 2 == 1, 2: ht_tot % 2 == 0}.get(n)

    if tid == 295 and ht_h is not None:  # Home scores both halves
        scored = ht_h > 0 and (h - ht_h) > 0
        return {1: scored, 2: not scored}.get(n)

    if tid == 296 and ht_a is not None:  # Away scores both halves
        scored = ht_a > 0 and (a - ht_a) > 0
        return {1: scored, 2: not scored}.get(n)

    if tid == 591 and ht_h is not None:  # Home wins both halves
        wins = ht_h > ht_a and (h - ht_h) > (a - ht_a)
        return {1: not wins, 2: wins}.get(n)

    if tid == 592 and ht_h is not None:  # Away wins both halves
        wins = ht_a > ht_h and (a - ht_a) > (h - ht_h)
        return {1: not wins, 2: wins}.get(n)

    if tid == 528 and ht_h is not None:  # Both halves Under 1.5
        h1_tot = ht_h + ht_a
        h2_tot = (h - ht_h) + (a - ht_a)
        ok = h1_tot < 1.5 and h2_tot < 1.5
        return {1: ok, 2: not ok}.get(n)

    if tid == 529 and ht_h is not None:  # Both halves Over 1.5
        h1_tot = ht_h + ht_a
        h2_tot = (h - ht_h) + (a - ht_a)
        ok = h1_tot > 1.5 and h2_tot > 1.5
        return {1: ok, 2: not ok}.get(n)

    if tid == 452 and ht_h is not None:  # 1st half BTTS: n=1→Yes, n=2→No
        scored = ht_h > 0 and ht_a > 0
        return {1: scored, 2: not scored}.get(n)

    if tid == 599 and ht_h is not None:  # 2nd half BTTS
        sh_h, sh_a = h - ht_h, a - ht_a
        scored = sh_h > 0 and sh_a > 0
        return {1: scored, 2: not scored}.get(n)

    if tid == 7 and ht_h is not None and ht_a is not None:   # HT result
        hfr = _fr(ht_h, ht_a)
        return {1: hfr == 1, 2: hfr == 0, 3: hfr == 2}.get(n)

    if tid == 9 and ht_h is not None and ht_a is not None:   # 2nd half result
        sfr = _fr(h - ht_h, a - ht_a)
        return {1: sfr == 1, 2: sfr == 0, 3: sfr == 2}.get(n)

    if tid in (14, 155, 209) and sov and ht_h is not None:   # 1st half O/U
        ht_tot = ht_h + (ht_a or 0)
        if n == 1: return ht_tot < sov
        if n == 2: return ht_tot > sov
        return None

    # Combined markets: 1X2 + O/U  (n follows: 1=1+Under,2=X+Under,3=2+Under,4=1+Over,5=X+Over,6=2+Over)
    if tid in (272, 342, 343, 438, 822) and sov:
        ou_half = tot < sov if n in (1, 2, 3) else tot > sov
        res_part = {1: fr == 1, 2: fr == 0, 3: fr == 2,
                    4: fr == 1, 5: fr == 0, 6: fr == 2}.get(n)
        if res_part is None: return None
        return res_part and ou_half

    # Combined: 1X2 + BTTS  (n: 1=1+Yes,2=1+No,3=X+Yes,4=X+No,5=2+Yes,6=2+No)
    if tid == 414:
        btts = h > 0 and a > 0
        btts_part = btts if n in (1, 3, 5) else not btts
        res_part = {1: fr == 1, 2: fr == 1, 3: fr == 0,
                    4: fr == 0, 5: fr == 2, 6: fr == 2}.get(n)
        if res_part is None: return None
        return res_part and btts_part
    # Combined: 1X2 + BTTS  (n: 1=1+Yes,2=X+Yes,3=2+Yes,4=1+No,5=X+No,6=2+No)
    if tid == 823:
        btts = h > 0 and a > 0
        btts_part = btts if n in (1, 2, 3) else not btts
        res_part = {1: fr == 1, 2: fr == 0, 3: fr == 2,
                    4: fr == 1, 5: fr == 0, 6: fr == 2}.get(n)
        if res_part is None: return None
        return res_part and btts_part

    # ── Additional score-based markets ────────────────────────────────────────

    if tid == 5 and ht_h is not None and ht_a is not None:   # HT/FT (9 combos)
        hfr   = _fr(ht_h, ht_a)
        combo = (hfr, fr)
        return {1: combo == (1, 1), 2: combo == (1, 0), 3: combo == (1, 2),
                4: combo == (0, 1), 5: combo == (0, 0), 6: combo == (0, 2),
                7: combo == (2, 1), 8: combo == (2, 0), 9: combo == (2, 2)}.get(n)

    if tid == 8 and ht_h is not None and ht_a is not None:   # 1st half double chance
        hfr = _fr(ht_h, ht_a)
        return {1: hfr in (1, 0), 2: hfr in (1, 2), 3: hfr in (0, 2)}.get(n)

    if tid == 214:   # Home clean sheet: n=1→Yes (away=0), n=2→No
        return {1: a == 0, 2: a > 0}.get(n)

    if tid == 215:   # Away clean sheet: n=1→Yes (home=0), n=2→No
        return {1: h == 0, 2: h > 0}.get(n)

    if tid in (442, 444):   # Win margin 2-way (no draw): n=1→Home, n=2→Away
        return {1: fr == 1, 2: fr == 2}.get(n, False)

    if tid in (461, 656):   # Result 2-way (no draw): n=1→Home, n=2→Away
        return {1: fr == 1, 2: fr == 2}.get(n, False)

    if tid == 446 and sov:   # O/U + BTTS: n=1→Alt&Var, n=2→Üst&Var, n=3→Alt&Yok, n=4→Üst&Yok
        ou   = tot < sov
        btts = h > 0 and a > 0
        return {1: ou and btts, 2: not ou and btts,
                3: ou and not btts, 4: not ou and not btts}.get(n)

    if tid == 824 and sov:   # Result + O/U + BTTS (triple combo)
        ou_p  = tot < sov if n in (1, 2, 3) else tot > sov
        bt_p  = h > 0 and a > 0
        res_p = {1: fr == 1, 2: fr == 0, 3: fr == 2,
                 4: fr == 1, 5: fr == 0, 6: fr == 2}.get(n)
        if res_p is None: return None
        return res_p and ou_p and bt_p

    if tid == 416 and ht_h is not None and ht_a is not None:   # 1st half result + BTTS
        hfr   = _fr(ht_h, ht_a)
        ht_bt = ht_h > 0 and ht_a > 0
        res_p = {1: hfr == 1, 2: hfr == 1, 3: hfr == 0,
                 4: hfr == 0, 5: hfr == 2, 6: hfr == 2}.get(n)
        bt_p  = ht_bt if n in (1, 3, 5) else not ht_bt
        if res_p is None: return None
        return res_p and bt_p

    if tid == 459 and sov and ht_h is not None and ht_a is not None:   # HT result + HT O/U
        hfr    = _fr(ht_h, ht_a)
        ht_tot = ht_h + ht_a
        ou_p   = ht_tot < sov if n in (1, 2, 3) else ht_tot > sov
        res_p  = {1: hfr == 1, 2: hfr == 0, 3: hfr == 2,
                  4: hfr == 1, 5: hfr == 0, 6: hfr == 2}.get(n)
        if res_p is None: return None
        return res_p and ou_p

    if tid == 457 and sov and ht_a is not None:   # Away 1st half O/U
        if n == 1: return ht_a < sov
        if n == 2: return ht_a > sov
        return None

    if tid == 584 and ht_h is not None and ht_a is not None:   # Home wins any half
        wins = (ht_h > ht_a) or ((h - ht_h) > (a - ht_a))
        return {1: wins, 2: not wins}.get(n)

    if tid == 585 and ht_h is not None and ht_a is not None:   # Away wins any half
        wins = (ht_a > ht_h) or ((a - ht_a) > (h - ht_h))
        return {1: wins, 2: not wins}.get(n)

    if tid == 586 and ht_h is not None:   # Home most goals half: n=1→1st, n=2→Equal, n=3→2nd
        h1, h2 = ht_h, h - ht_h
        hw = 1 if h1 > h2 else (3 if h1 < h2 else 2)
        return {1: hw == 1, 2: hw == 2, 3: hw == 3}.get(n)

    if tid == 587 and ht_a is not None:   # Away most goals half: n=1→1st, n=2→Equal, n=3→2nd
        a1, a2 = ht_a, a - ht_a
        aw = 1 if a1 > a2 else (3 if a1 < a2 else 2)
        return {1: aw == 1, 2: aw == 2, 3: aw == 3}.get(n)

    if tid == 589:   # Home wins to nil: n=1→by 1 (1-0), n=2→by 2+ (2-0, 3-0…)
        if n == 1: return a == 0 and h == 1
        if n == 2: return a == 0 and h >= 2
        return None

    if tid == 590:   # Away clean sheet win: n=1→Yes, n=2→No
        wins_nil = a > h and h == 0
        return {1: wins_nil, 2: not wins_nil}.get(n)

    if tid == 801 and ht_h is not None and ht_a is not None:   # Both halves BTTS
        h1_bt = ht_h > 0 and ht_a > 0
        h2_bt = (h - ht_h) > 0 and (a - ht_a) > 0
        return {1: not h1_bt and not h2_bt, 2: h1_bt and not h2_bt,
                3: h1_bt and h2_bt,         4: not h1_bt and h2_bt}.get(n)

    # ── Statistics-based markets (require enriched result) ────────────────────
    stats = result.get("statistics") or {}
    hs    = stats.get("home") or {}
    as_   = stats.get("away") or {}

    # ── Corners — commentary-derived (first corner + per-half splits) ─────────
    if tid == 224:   # First corner: n=1→Home, n=2→Away
        fct = result.get("firstCornerTeam")
        if fct is None: return None
        return {1: fct == 1, 2: fct == 2}.get(n)

    h1c = result.get("h1Corners") or {}
    h1_hc = h1c.get("home", 0)
    h1_ac = h1c.get("away", 0)
    h1_tc = h1_hc + h1_ac

    if tid == 222:   # 1st half most corners: n=1→Home, n=2→X, n=3→Away
        if not h1c: return None
        if h1_hc > h1_ac: w = 1
        elif h1_ac > h1_hc: w = 2
        else: w = 0
        return {1: w == 1, 2: w == 0, 3: w == 2}.get(n)

    if tid == 340 and h1c:   # 1st half corner range: n=1→0-4, n=2→5-6, n=3→7+
        return {1: h1_tc <= 4, 2: 5 <= h1_tc <= 6, 3: h1_tc >= 7}.get(n)

    if tid == 862 and sov and h1c:   # 1st half total corners O/U
        if n == 1: return h1_tc < sov
        if n == 2: return h1_tc > sov
        return None

    if tid == 799 and sov and h1c:   # 1st half corner Asian handicap
        adj = h1_hc + sov
        if adj > h1_ac: return {1: True, 2: False}.get(n)
        if adj < h1_ac: return {1: False, 2: True}.get(n)
        return None   # push on integer spread

    # ── Corners — full-match (from team statistics) ────────────────────────────
    if tid in (216, 424, 583, 338, 220, 299, 426, 601, 602, 798, 864, 867):
        if not hs and not as_:
            return None
        hc = int(hs.get("corners") or 0)
        ac = int(as_.get("corners") or 0)
        tc = hc + ac

        if tid in (216, 424) and sov:   # Total corners O/U
            if n == 1: return tc < sov
            if n == 2: return tc > sov
            return None

        if tid == 338:   # Total corners range: n=1→0-8, n=2→9-11, n=3→12+
            return {1: tc <= 8, 2: 9 <= tc <= 11, 3: tc >= 12}.get(n)

        if tid == 583 and sov:   # Multi-line corners O/U: odd n→Over, even n→Under
            if n % 2 == 1: return tc > sov
            if n % 2 == 0: return tc < sov
            return None

        if tid == 867:   # Corners 1X2: n=1→Home, n=2→X, n=3→Away
            cfr = 1 if hc > ac else (2 if hc < ac else 0)
            return {1: cfr == 1, 2: cfr == 0, 3: cfr == 2}.get(n)

        if tid == 220:   # Most corners 1X2: n=1→Home, n=2→X(Equal), n=3→Away
            if hc > ac: w = 1
            elif ac > hc: w = 2
            else: w = 0
            return {1: w == 1, 2: w == 0, 3: w == 2}.get(n)

        if tid == 299:   # Corners odd/even: n=1→Odd, n=2→Even
            return {1: tc % 2 == 1, 2: tc % 2 == 0}.get(n)

        if tid == 601 and sov:   # Home corners O/U
            if n == 1: return hc < sov
            if n == 2: return hc > sov
            return None

        if tid == 602 and sov:   # Away corners O/U
            if n == 1: return ac < sov
            if n == 2: return ac > sov
            return None

        if tid == 798 and sov:   # Corners Asian handicap (home+sov vs away, no push on .5)
            adj = hc + sov
            if adj > ac: return {1: True, 2: False}.get(n)
            if adj < ac: return {1: False, 2: True}.get(n)
            return None   # push on integer spread

        if tid in (864, 426) and sov:   # Team corner European handicap
            adj = hc + sov
            cfr = 1 if adj > ac else (2 if adj < ac else 0)
            return {1: cfr == 1, 2: cfr == 0, 3: cfr == 2}.get(n)

    # ── Cards ─────────────────────────────────────────────────────────────────
    if tid in (225, 218, 301, 863, 603):
        if not hs and not as_:
            return None
        h_yel = int(hs.get("yellowCards") or 0)
        a_yel = int(as_.get("yellowCards") or 0)
        h_red = int(hs.get("redCards") or 0)
        a_red = int(as_.get("redCards") or 0)
        t_red = h_red + a_red
        h_cp  = h_yel + h_red * 2   # card points: Yellow=1, Red=2
        a_cp  = a_yel + a_red * 2
        t_cp  = h_cp + a_cp

        if tid == 225:   # Red card in match: n=1→Yes, n=2→No
            return {1: t_red > 0, 2: t_red == 0}.get(n)

        if tid in (218, 301, 863) and sov:   # Full-match card points O/U
            if n == 1: return t_cp < sov
            if n == 2: return t_cp > sov
            return None

        if tid == 603:   # Most card points: n=1→Home, n=2→Away, n=3→Equal
            if   h_cp > a_cp: cw = 1
            elif a_cp > h_cp: cw = 2
            else:             cw = 3
            return {1: cw == 1, 2: cw == 2, 3: cw == 3}.get(n)

    # ── Shots (total / on target) O/U ─────────────────────────────────────────
    if tid in (805, 806):
        if not hs and not as_:
            return None
        raw_label = (bet.get("outcomeLabel") or "").strip()
        key = "totalShots" if tid == 805 else "shotsOnGoal"
        team_name, thr, is_over = _parse_label_threshold(raw_label)
        effective_sov = thr if thr is not None else sov
        if not effective_sov:
            return None
        # Identify home vs away by matching team name against matchNameEn / matchName
        def _nn(s): return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
        mn = bet.get("matchNameEn") or bet.get("matchName") or ""
        mn_parts = mn.split(" vs ", 1)
        if len(mn_parts) == 2 and team_name:
            tn = _nn(team_name)
            away_n = _nn(mn_parts[1].strip())
            side_stats = as_ if (tn in away_n or away_n in tn) else hs
        else:
            lbl_l = raw_label.lower()
            side_stats = as_ if ("away" in lbl_l or "deplasman" in lbl_l) else hs
        shots = int(side_stats.get(key) or 0)
        if is_over is not None:
            return shots >= effective_sov if is_over else shots < effective_sov
        if n == 1: return shots < effective_sov
        if n == 2: return shots >= effective_sov
        return None

    # ── Goalkeeper saves O/U (typeId 803) ────────────────────────────────────
    if tid == 803:
        if not hs and not as_: return None
        raw_label = (bet.get("outcomeLabel") or "").strip()
        _, thr, is_over = _parse_label_threshold(raw_label)
        effective_sov = thr if thr is not None else sov
        if not effective_sov:
            return None
        total_saves = int(hs.get("saves") or 0) + int(as_.get("saves") or 0)
        if is_over is not None:
            return total_saves >= effective_sov if is_over else total_saves < effective_sov
        if n == 1: return total_saves < effective_sov
        if n == 2: return total_saves > effective_sov
        return None

    # ── Team fouls / offsides / possession O/U (807/808/809) ─────────────────
    if tid in (807, 808, 809) and sov:
        if not hs and not as_: return None
        lbl  = (bet.get("outcomeLabel") or "").lower()
        side = as_ if ("away" in lbl or "deplasman" in lbl) else hs
        key  = "fouls" if tid == 807 else ("offsides" if tid == 808 else "possession")
        val  = int(side.get(key) or 0)
        if n == 1: return val < sov
        if n == 2: return val > sov
        return None

    # ── VAR decisions O/U (typeId 804) — from commentary ────────────────────
    if tid == 804 and sov:
        var_count = result.get("varDecisions")
        if var_count is None: return None
        if n == 1: return var_count < sov
        if n == 2: return var_count > sov
        return None

    # ── 1st half card points O/U (typeId 800) — uses card event timing ───────
    if tid == 800 and sov:
        card_events = result.get("cardEvents") or []
        if not card_events: return None
        # prefer explicit period field (ESPN); fall back to time<=45 (api-football)
        _chalf = lambda ev: ev.get("period") or (1 if (ev.get("time") or 0) <= 45 else 2)
        h1_cp = sum(
            (1 if ev.get("type") == "yellow" else 2)
            for ev in card_events if _chalf(ev) == 1
        )
        if n == 1: return h1_cp < sov
        if n == 2: return h1_cp > sov
        return None

    # ── First team to score (typeId 291) ──────────────────────────────────────
    if tid == 291:
        fgt = result.get("firstGoalTeam")
        # n=1→Home first, n=2→No goal, n=3→Away first
        if tot == 0:
            return {2: True}.get(n, False)
        return {1: fgt == 1, 2: False, 3: fgt == 2}.get(n)

    # ── Exact score (777=FT, 779=HT) ─────────────────────────────────────────
    if tid == 777:
        label = (bet.get("outcomeLabel") or "").strip()
        parts = label.split(":")
        if len(parts) == 2:
            try:
                return int(parts[0]) == h and int(parts[1]) == a
            except ValueError:
                pass
        return None

    if tid == 779 and ht_h is not None and ht_a is not None:
        label = (bet.get("outcomeLabel") or "").strip()
        parts = label.split(":")
        if len(parts) == 2:
            try:
                return int(parts[0]) == ht_h and int(parts[1]) == ht_a
            except ValueError:
                pass
        return None

    if tid == 571 and ht_h is not None and ht_a is not None:   # HT/FT exact score combo e.g. "1-0 / 2-1"
        label = (bet.get("outcomeLabel") or "").strip()
        nums  = re.findall(r'\d+', label)
        if len(nums) >= 4:
            try:
                lht_h, lht_a, lft_h, lft_a = int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3])
                return ht_h == lht_h and ht_a == lht_a and h == lft_h and a == lft_a
            except (ValueError, IndexError):
                pass
        return None

    # ── Player markets ────────────────────────────────────────────────────────
    players = result.get("players") or {}
    label   = (bet.get("outcomeLabel") or "").strip()

    if tid == 701:   # Player scores anytime
        if not players: return None
        p = _ko_find_player(players, label)
        return (p["goals"] > 0) if p else None

    if tid == 702:   # First goal scorer
        if not players: return None
        fgp = result.get("firstGoalPlayer") or ""
        if not fgp: return None
        def _nn(s): return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
        q_parts = _nn(label).split()
        f_parts = _nn(fgp).split()
        return bool(q_parts and f_parts and q_parts[-1] == f_parts[-1])

    if tid == 703:   # Player scores in both halves
        goal_scorers = result.get("goalScorers") or []
        if not goal_scorers: return None
        def _nn(s): return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()
        label_q = _nn(label)
        q_parts = label_q.split()
        def _gs_match(name):
            nk = _nn(name or "")
            if nk == label_q: return True
            n_parts = nk.split()
            if q_parts and n_parts and q_parts[-1] == n_parts[-1]: return True
            return label_q in nk or nk in label_q
        player_goals = [g for g in goal_scorers if _gs_match(g.get("player", ""))]
        if not player_goals: return None
        # prefer explicit period field (ESPN); fall back to time<=45 (api-football)
        _ghalf = lambda g: g.get("period") or (1 if (g.get("time") or 0) <= 45 else 2)
        scored_h1 = any(_ghalf(g) == 1 for g in player_goals)
        scored_h2 = any(_ghalf(g) == 2 for g in player_goals)
        return scored_h1 and scored_h2

    if tid in (704, 710):   # Player yellow card
        if not players: return None
        p = _ko_find_player(players, label)
        return (p["yellowCards"] > 0) if p else None

    if tid == 709:   # Player red card
        if not players: return None
        p = _ko_find_player(players, label)
        return (p["redCards"] > 0) if p else None

    if tid == 722:   # Player any card
        if not players: return None
        p = _ko_find_player(players, label)
        return ((p["yellowCards"] + p["redCards"]) > 0) if p else None

    if tid == 837:   # Player 2+ cards
        if not players: return None
        p = _ko_find_player(players, label)
        return ((p["yellowCards"] + p["redCards"]) >= 2) if p else None

    if tid == 707:   # Player assist
        if not players: return None
        p = _ko_find_player(players, label)
        return (p["assists"] > 0) if p else None

    if tid == 714:   # Player shots on target (label: "Name N+" or just "Name")
        if not players: return None
        name_part, thr, is_over = _parse_label_threshold(label)
        p = _ko_find_player(players, name_part or label)
        if not p: return None
        shots = p["shotsOnTarget"]
        if thr is not None:
            return shots >= thr if is_over else shots < thr
        return shots > 0

    if tid == 740:   # Player total shots (label: "Name N+" or just "Name")
        if not players: return None
        name_part, thr, is_over = _parse_label_threshold(label)
        p = _ko_find_player(players, name_part or label)
        if not p: return None
        shots = p["totalShots"]
        if thr is not None:
            return shots >= thr if is_over else shots < thr
        return shots > 0

    if tid == 705:   # Player goal + team wins
        if not players: return None
        p = _ko_find_player(players, label)
        if not p: return None
        team_won = (fr == 1 and p["team"] == 1) or (fr == 2 and p["team"] == 2)
        return p["goals"] > 0 and team_won

    if tid == 711:   # Player goal + gets a card
        if not players: return None
        p = _ko_find_player(players, label)
        if not p: return None
        return p["goals"] > 0 and (p["yellowCards"] + p["redCards"]) > 0

    if tid == 713:   # Player goal + assist
        if not players: return None
        p = _ko_find_player(players, label)
        if not p: return None
        return p["goals"] > 0 and p["assists"] > 0

    if tid == 765:   # Player goal or assist
        if not players: return None
        p = _ko_find_player(players, label)
        if not p: return None
        return p["goals"] > 0 or p["assists"] > 0

    if tid == 740:   # Player takes a shot (total shots > 0)
        if not players: return None
        p = _ko_find_player(players, label)
        return (p["totalShots"] > 0) if p else None

    if tid == 741:   # Player draws a foul
        if not players: return None
        p = _ko_find_player(players, label)
        return (p["foulsDrawn"] > 0) if p else None

    if tid == 743:   # Player caught offside
        if not players: return None
        p = _ko_find_player(players, label)
        if not p: return None
        ofs = p.get("offsides")
        if ofs is None: return None
        return ofs > 0

    if tid == 712:   # Player gets an assist (binary yes/no, cf. 707)
        if not players: return None
        p = _ko_find_player(players, label)
        return (p["assists"] > 0) if p else None

    if tid == 742:   # Player commits a foul
        if not players: return None
        p = _ko_find_player(players, label)
        return (p["foulsCommitted"] > 0) if p else None

    if tid in (706, 708):   # Player header goal (706) / free-kick goal (708)
        goal_scorers = result.get("goalScorers")
        if goal_scorers is None: return None   # data not fetched
        label_q = label.lower().strip()
        q_parts = label_q.split()
        def _gsn(name):
            nk = (name or "").lower().strip()
            n_parts = nk.split()
            return (nk == label_q or
                    (q_parts and n_parts and q_parts[-1] == n_parts[-1]) or
                    label_q in nk or nk in label_q)
        target_detail = "goal---header" if tid == 706 else "goal---free-kick"
        return any(_gsn(g.get("player", "")) and g.get("detail") == target_detail
                   for g in goal_scorers)

    return None


def _ko_espn_get(url):
    """Single GET to ESPN public API (no authentication required)."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ko_espn_process_events(key_events, home_id):
    """Extract structured goal/card events from ESPN keyEvents array."""
    first_goal     = None
    goal_scorers   = []
    card_events    = []
    penalty_events = []

    GOAL_TYPES = {"goal", "goal---header", "goal---free-kick",
                  "goal---penalty", "goal---own-goal"}

    for ev in key_events:
        ev_type = (ev.get("type") or {}).get("type", "")
        if not ev_type:
            continue

        # Parse display minute; handles stoppage time "45+2'" correctly
        clock_disp = (ev.get("clock") or {}).get("displayValue", "").replace("'", "").strip()
        period_num = (ev.get("period") or {}).get("number", 1)
        try:
            if "+" in clock_disp:
                base_min, extra = clock_disp.split("+", 1)
                minute = int(base_min.strip()) + int(extra.strip())
            else:
                minute = int(clock_disp) if clock_disp else 0
        except (ValueError, TypeError):
            minute = int((ev.get("clock") or {}).get("value", 0) or 0) // 60

        team_id  = (ev.get("team") or {}).get("id")
        side     = 1 if team_id == home_id else 2
        parts    = ev.get("participants") or []
        scorer   = (parts[0].get("athlete") or {}).get("displayName", "") if parts else ""
        assister = (parts[1].get("athlete") or {}).get("displayName", "") if len(parts) > 1 else ""

        if ev_type in GOAL_TYPES and ev.get("scoringPlay"):
            if first_goal is None:
                first_goal = {"team": side, "player": scorer, "time": minute}
            goal_scorers.append({
                "player": scorer, "assist": assister,
                "team": side, "time": minute, "period": period_num,
                "detail": ev_type,
            })
            if "penalty" in ev_type:
                penalty_events.append({"team": side, "result": "scored", "time": minute})

        elif ev_type == "yellow-card":
            card_events.append({
                "player": scorer, "team": side,
                "time": minute, "period": period_num, "type": "yellow",
            })

        elif ev_type == "red-card":
            card_events.append({
                "player": scorer, "team": side,
                "time": minute, "period": period_num, "type": "red",
            })

    return {
        "firstGoalTeam":   first_goal["team"]   if first_goal else None,
        "firstGoalPlayer": first_goal["player"] if first_goal else None,
        "goalScorers":     goal_scorers,
        "cardEvents":      card_events,
        "penaltyEvents":   penalty_events,
    }


def _ko_espn_process_statistics(boxscore_teams):
    """Map ESPN boxscore team statistics to compact {home:{...}, away:{...}}."""
    out = {"home": {}, "away": {}}

    def _iv(sm, key, default=0):
        val = sm.get(key)
        if val is None:
            return default
        try:
            return int(float(str(val)))
        except (ValueError, TypeError):
            return default

    for team_data in boxscore_teams:
        side = team_data.get("homeAway", "away")
        sm   = {s["name"]: s.get("displayValue")
                for s in team_data.get("statistics", []) if "name" in s}
        out[side] = {
            "corners":     _iv(sm, "wonCorners"),
            "fouls":       _iv(sm, "foulsCommitted"),
            "yellowCards": _iv(sm, "yellowCards"),
            "redCards":    _iv(sm, "redCards"),
            "offsides":    _iv(sm, "offsides"),
            "saves":       _iv(sm, "saves"),
            "possession":  _iv(sm, "possessionPct"),
            "totalShots":  _iv(sm, "totalShots"),
            "shotsOnGoal": _iv(sm, "shotsOnTarget"),   # ESPN name → our internal key
            "blockedShots":_iv(sm, "blockedShots"),
        }

    return out


def _ko_espn_process_players(rosters):
    """Return lowercase-name-keyed dict of per-player stats from ESPN rosters."""
    players = {}

    for roster_entry in rosters:
        side = 1 if roster_entry.get("homeAway") == "home" else 2
        for entry in roster_entry.get("roster", []):
            athlete = entry.get("athlete") or {}
            name    = athlete.get("displayName", "")
            if not name:
                continue
            sm = {s["name"]: (s.get("value") or 0.0)
                  for s in entry.get("stats", []) if "name" in s}
            players[name.lower()] = {
                "name":           name,
                "team":           side,
                "playerId":       athlete.get("id"),
                "goals":          int(sm.get("totalGoals",     0) or 0),
                "assists":        int(sm.get("goalAssists",    0) or 0),
                "shotsOnTarget":  int(sm.get("shotsOnTarget",  0) or 0),
                "totalShots":     int(sm.get("totalShots",     0) or 0),
                "yellowCards":    int(sm.get("yellowCards",    0) or 0),
                "redCards":       int(sm.get("redCards",       0) or 0),
                "foulsDrawn":     int(sm.get("foulsSuffered",  0) or 0),
                "foulsCommitted": int(sm.get("foulsCommitted", 0) or 0),
                "offsides":       int(sm.get("offsides",       0) or 0),
                "penaltyScored":  0,
                "penaltyMissed":  0,
            }

    return players


def _ko_espn_process_commentary(commentary, home_name_lower):
    """Extract VAR decisions and per-period corner data from ESPN commentary array."""
    var_decisions   = 0
    first_corner    = None
    h1_corners      = {"home": 0, "away": 0}
    h2_corners      = {"home": 0, "away": 0}

    for entry in commentary:
        play   = entry.get("play") or {}
        ptype  = (play.get("type") or {}).get("type", "")
        period = (play.get("period") or {}).get("number", 1)

        if ptype == "var---referee-decision-cancelled":
            var_decisions += 1

        elif ptype == "corner-awarded":
            tname = (play.get("team") or {}).get("displayName", "").lower()
            side  = "home" if tname == home_name_lower else "away"
            if first_corner is None:
                first_corner = 1 if side == "home" else 2
            bucket = h1_corners if period == 1 else h2_corners
            bucket[side] += 1

    return {
        "varDecisions":   var_decisions,
        "firstCornerTeam": first_corner,
        "h1Corners":      h1_corners,
        "h2Corners":      h2_corners,
    }


def _ko_fetch_match_result_for_log_entry(minfo):
    """Fetch full match data from ESPN public API (free, no key required)."""
    cfg  = CONFIG.get("ko_results_api", {})
    slug = cfg.get("competition_slug", "fifa.world")
    base = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}"

    start_ts = minfo.get("startTimestamp")
    if not start_ts:
        return None
    try:
        ts_f   = float(start_ts)
        ts_sec = ts_f / 1000.0 if ts_f > 1e10 else ts_f
    except (ValueError, TypeError):
        return None

    dt       = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
    date_str = dt.strftime("%Y%m%d")   # ESPN format: YYYYMMDD, no dashes

    name  = _match_name_en(minfo)
    parts = name.split(" vs ", 1)
    if len(parts) != 2:
        return None
    t1 = parts[0].strip().lower()
    t2 = parts[1].strip().lower()

    # ── Step 1: scoreboard → find event_id by date + fuzzy team name ─────────
    # ESPN uses US Eastern time so a match at 00:xx UTC may appear under the previous date.
    prev_date_str = (dt - timedelta(days=1)).strftime("%Y%m%d")
    dates_to_try  = [date_str, prev_date_str]

    event_id       = None
    finished_lower = {"full time", "after extra time", "after penalties", "final"}

    def _norm(s):
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

    for try_date in dates_to_try:
        try:
            sb = _ko_espn_get(f"{base}/scoreboard?dates={try_date}&limit=50")
        except Exception as exc:
            print(f"[ko-espn] scoreboard {try_date}: {exc}")
            continue
        for ev in sb.get("events", []):
            comps  = ev.get("competitions") or [{}]
            status = (comps[0].get("status") or {}).get("type", {}).get("description", "").lower()
            if not any(s in status for s in finished_lower):
                continue
            teams = comps[0].get("competitors") or []
            names = {t.get("homeAway"): _norm((t.get("team") or {}).get("displayName", ""))
                     for t in teams}
            hn = names.get("home", "")
            an = names.get("away", "")
            t1n, t2n = _norm(t1), _norm(t2)
            def _names_match(a, b):
                if a in b or b in a:
                    return True
                # token overlap: any significant word (>3 chars) shared
                ta = set(w for w in a.split() if len(w) > 3)
                tb = set(w for w in b.split() if len(w) > 3)
                return bool(ta & tb)
            if _names_match(t1n, hn) and _names_match(t2n, an):
                event_id = ev.get("id")
                break
        if event_id:
            break

    if not event_id:
        print(f"[ko-espn] match not found: '{t1}' vs '{t2}' on {date_str}/{prev_date_str}")
        return None

    # ── Step 2: full summary — one call for all data ──────────────────────────
    try:
        d = _ko_espn_get(f"{base}/summary?event={event_id}")
    except Exception as exc:
        print(f"[ko-espn] summary {event_id}: {exc}")
        return None

    # ── Step 3: scores + HT scores from header competitors ───────────────────
    hdr      = d.get("header") or {}
    comp_hdr = (hdr.get("competitions") or [{}])[0]
    status_d = (comp_hdr.get("status") or {}).get("type", {}).get("description", "").lower()
    if "after penalties" in status_d:
        status_short = "PEN"
    elif "after extra time" in status_d:
        status_short = "AET"
    else:
        status_short = "FT"

    h_goals = a_goals = ht_h = ht_a = pen_h = pen_a = home_id = home_name = None
    agg_h   = agg_a   = None

    for team in comp_hdr.get("competitors") or []:
        ha  = team.get("homeAway", "")
        ls  = team.get("linescores") or []
        try:
            sc = int(team.get("score") or 0)
        except (ValueError, TypeError):
            continue
        ht_val = None
        if ls:
            try:
                ht_val = int(ls[0].get("displayValue") or 0)
            except (ValueError, TypeError):
                pass
        # ESPN's "score" aggregates extra-time goals too once a match goes to
        # AET/PEN, but standard markets (1X2, O/U, combos, ...) settle on the
        # 90-minute regulation score — so sum just the first two periods when
        # they're present, and keep the true aggregate separately for the
        # "Who Advances" market, which does care about the AET result.
        reg_val = sc
        if len(ls) >= 2:
            try:
                reg_val = int(ls[0].get("displayValue") or 0) + int(ls[1].get("displayValue") or 0)
            except (ValueError, TypeError):
                pass
        pen_val = None
        if status_short == "PEN" and len(ls) >= 5:
            try:
                pen_val = int(ls[-1].get("displayValue") or 0)
            except (ValueError, TypeError):
                pass
        if ha == "home":
            h_goals = reg_val
            agg_h   = sc
            ht_h    = ht_val
            pen_h   = pen_val
            home_id   = (team.get("team") or {}).get("id")
            home_name = (team.get("team") or {}).get("displayName", "").lower()
        else:
            a_goals = reg_val
            agg_a   = sc
            ht_a    = ht_val
            pen_a   = pen_val

    if h_goals is None or a_goals is None:
        return None

    result = {
        "homeGoals":    h_goals,
        "awayGoals":    a_goals,
        "aggHomeGoals": agg_h,
        "aggAwayGoals": agg_a,
        "htHomeGoals":  ht_h,
        "htAwayGoals":  ht_a,
        "penHome":      pen_h,
        "penAway":      pen_a,
        "status":       status_short,
        "eventId":      event_id,
    }

    # ── Step 4: goal / card events ────────────────────────────────────────────
    result.update(_ko_espn_process_events(d.get("keyEvents") or [], home_id))

    # ── Step 5: team statistics (corners, shots, fouls, possession, etc.) ─────
    result["statistics"] = _ko_espn_process_statistics(
        (d.get("boxscore") or {}).get("teams") or []
    )

    # ── Step 6: per-player statistics ─────────────────────────────────────────
    result["players"] = _ko_espn_process_players(d.get("rosters") or [])

    # ── Step 7: commentary (VAR decisions + per-period corner events) ─────────
    result.update(_ko_espn_process_commentary(
        d.get("commentary") or [], home_name or ""))

    return result


def _ko_bet_result_detail(bet, result):
    """Return a human-readable string of the actual stat for the bet outcome, or None."""
    if not result:
        return None
    tid   = int(bet.get("typeId") or 0)
    label = (bet.get("outcomeLabel") or "").strip()
    players = result.get("players") or {}
    stats   = result.get("statistics") or {}
    h_goals = result.get("homeGoals")
    a_goals = result.get("awayGoals")

    def _nn(s):
        return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().strip()

    # ── Player stat markets ───────────────────────────────────────────────────
    _player_stats = {
        701: ("goals",         "gol"),
        702: ("goals",         "gol"),
        703: ("goals",         "gol"),
        704: ("yellowCards",   "sarı kart"),
        709: ("redCards",      "kırmızı kart"),
        710: ("yellowCards",   "sarı kart"),
        707: ("assists",       "asist"),
        711: ("goals",         "gol"),
        712: ("assists",       "asist"),
        713: ("goals",         "gol"),
        714: ("shotsOnTarget", "isabetli şut"),
        740: ("totalShots",    "şut"),
    }
    if tid in _player_stats:
        stat_key, stat_label = _player_stats[tid]
        name_part, thr, _ = _parse_label_threshold(label)
        player_name = name_part or label
        p = _ko_find_player(players, player_name)
        if p:
            val = p.get(stat_key, 0)
            return f"{p['name']}: {val} {stat_label}"
        if tid == 702:
            fgp = result.get("firstGoalPlayer") or ""
            if fgp:
                return f"İlk gol: {fgp}"
        return None

    # ── Team shots markets ────────────────────────────────────────────────────
    if tid in (805, 806):
        name_part, thr, _ = _parse_label_threshold(label)
        key = "totalShots" if tid == 805 else "shotsOnGoal"
        stat_label = "şut" if tid == 805 else "isabetli şut"
        mn = bet.get("matchNameEn") or bet.get("matchName") or ""
        mn_parts = mn.split(" vs ", 1)
        if len(mn_parts) == 2 and name_part:
            tn = _nn(name_part)
            away_n = _nn(mn_parts[1].strip())
            side = "away" if (tn in away_n or away_n in tn) else "home"
        else:
            side = "home"
        val = (stats.get(side) or {}).get(key)
        if val is not None:
            return f"{name_part}: {val} {stat_label}"
        return None

    # ── Score markets ─────────────────────────────────────────────────────────
    if tid in (777, 779, 571) and h_goals is not None:
        ht_h = result.get("htHomeGoals")
        ht_a = result.get("htAwayGoals")
        if tid == 779 and ht_h is not None:
            return f"HT: {ht_h}-{ht_a}"
        return f"FT: {h_goals}-{a_goals}"

    return None


def _ko_settle_match_bets(match_id, result):
    """Settle all users' bets for a finished match."""
    with _data_lock:
        bets_data = _jload(_KO_BETS_FILE, {"bets": {}})
        changed   = False
        for user_bets in bets_data.get("bets", {}).values():
            bet = user_bets.get(match_id)
            if not bet or "won" in bet:
                continue
            won = _ko_settle_bet(bet, result)
            if won is not None:
                bet["won"]       = won
                bet["payout"]    = round(float(bet.get("amount", 0)) * float(bet.get("odds", 1)), 2) if won else 0.0
                bet["settledAt"] = datetime.now(timezone.utc).isoformat()
                changed = True
        if changed:
            _jsave(_KO_BETS_FILE, bets_data)


def _ko_check_and_settle_finished_matches():
    """Fetch results and settle bets for each match that started >105 minutes ago."""
    now_ts = time.time()
    log    = _jload(_KO_MATCH_LOG_FILE, {"matches": {}})

    for match_id, minfo in list(log["matches"].items()):
        res_data = _jload(_KO_RESULTS_FILE, {"results": {}})
        if match_id in res_data.get("results", {}):
            _ko_settle_match_bets(match_id, res_data["results"][match_id])
            continue

        start_ts = minfo.get("startTimestamp")
        if not start_ts:
            continue
        try:
            ts_f   = float(start_ts)
            ts_sec = ts_f / 1000.0 if ts_f > 1e10 else ts_f
        except (ValueError, TypeError):
            continue
        if now_ts < ts_sec + 105 * 60:
            continue

        result = _ko_fetch_match_result_for_log_entry(minfo)
        if not result:
            continue

        with _data_lock:
            res_data = _jload(_KO_RESULTS_FILE, {"results": {}})
            if match_id not in res_data.get("results", {}):
                res_data.setdefault("results", {})[match_id] = {
                    **result,
                    "matchName": minfo.get("name", ""),
                    "fetchedAt": datetime.now(timezone.utc).isoformat(),
                }
                _jsave(_KO_RESULTS_FILE, res_data)
                print(f"[ko-results] {minfo.get('name', match_id)}: "
                      f"{result['homeGoals']}-{result['awayGoals']} ({result['status']})")

        _ko_settle_match_bets(match_id, result)


_ko_last_settle_ts   = 0.0
_ko_settle_ts_lock   = threading.Lock()

def _ko_maybe_settle():
    """Throttled wrapper — runs at most once every 5 minutes."""
    global _ko_last_settle_ts
    with _ko_settle_ts_lock:
        if time.time() - _ko_last_settle_ts < 300:
            return
        _ko_last_settle_ts = time.time()
    _ko_check_and_settle_finished_matches()


def _ko_compute_leaderboard():
    users_data = _jload(_USERS_FILE, {"users": {}})
    lb = []
    for uname, uinfo in users_data.get("users", {}).items():
        credit   = _ko_compute_credit(uname, count_pending=False)
        bets_all = _jload(_KO_BETS_FILE, {"bets": {}}).get("bets", {}).get(uname, {})
        lb.append({
            "username":      uname,
            "displayName":   uinfo.get("displayName", uname),
            "supportedTeam": uinfo.get("supportedTeam"),
            "hasLogo":       bool(uinfo.get("logoData")),
            "credit":        round(credit, 2),
            "bets":          len(bets_all),
            "won":           sum(1 for b in bets_all.values() if b.get("won") is True),
            "lost":          sum(1 for b in bets_all.values() if b.get("won") is False),
        })
    lb.sort(key=lambda x: -x["credit"])
    return lb


# ── Scoring ────────────────────────────────────────────────────────────────────
def _calc_points(guess, result_score, fh_answer, sh_answer):
    pts = {"score": 0, "result": 0, "fhBonus": 0, "shBonus": 0, "total": 0}
    if not guess or not result_score:
        return pts
    cfg = POINTS_CFG
    gh, ga = guess.get("homeScore"), guess.get("awayScore")
    rh, ra = result_score.get("home"),  result_score.get("away")
    if None not in (gh, ga, rh, ra):
        if gh == rh and ga == ra:
            pts["score"]  = cfg.get("correct_score",  5)
            pts["result"] = cfg.get("correct_result", 3)
        elif ((gh > ga and rh > ra) or
              (gh == ga and rh == ra) or
              (gh < ga and rh < ra)):
            pts["result"] = cfg.get("correct_result", 3)
    def _norm(v):
        return str(v).strip().lower() if v is not None else ""
    if _norm(guess.get("fhBonus")) and _norm(fh_answer) and \
            _norm(guess.get("fhBonus")) == _norm(fh_answer):
        pts["fhBonus"] = cfg.get("correct_fh_bonus", 1)
    if _norm(guess.get("shBonus")) and _norm(sh_answer) and \
            _norm(guess.get("shBonus")) == _norm(sh_answer):
        pts["shBonus"] = cfg.get("correct_sh_bonus", 1)
    pts["total"] = sum(pts[k] for k in ("score", "result", "fhBonus", "shBonus"))
    return pts


def _compute_leaderboard():
    guesses_data = _jload(_GUESS_FILE, {"guesses": {}})
    results_data = _jload(_RES_FILE,   {"results": {}})
    users_data   = _jload(_USERS_FILE, {"users": {}})
    results  = results_data.get("results", {})
    lb = []
    for uname, uinfo in users_data.get("users", {}).items():
        user_guesses = guesses_data.get("guesses", {}).get(uname, {})
        total = 0
        match_pts = {}
        for idx_s, res in results.items():
            g = user_guesses.get(idx_s)
            if g:
                p = _calc_points(g, res.get("score"),
                                 res.get("fhBonusAnswer"), res.get("shBonusAnswer"))
                match_pts[idx_s] = p
                total += p["total"]
        lb.append({"username": uname,
                   "displayName": uinfo.get("displayName", uname),
                   "supportedTeam": uinfo.get("supportedTeam"),
                   "logoData": uinfo.get("logoData"),
                   "totalPoints": total, "matchPoints": match_pts})
    lb.sort(key=lambda x: -x["totalPoints"])

    # Honor user pinned at #1 with the theoretical maximum points for group stage.
    max_per_match = (
        POINTS_CFG.get("correct_score", 5)
        + POINTS_CFG.get("correct_result", 3)
        + POINTS_CFG.get("correct_fh_bonus", 1)
        + POINTS_CFG.get("correct_sh_bonus", 1)
    )
    honor_total = len(_GROUP_MATCHES) * max_per_match
    lb.insert(0, {
        "username": "honor_pa_pa",
        "displayName": "Pa&Pa",
        "supportedTeam": "Belgium",
        "logoData": "/img/papa.png",
        "totalPoints": honor_total,
        "matchPoints": {},
    })
    return lb


def _fetch_result_api(match):
    """Try football-data.org for a finished result."""
    cfg     = CONFIG.get("results_api", {})
    api_key = cfg.get("api_key", "")
    if not api_key:
        return None
    base = cfg.get("base_url", "https://api.football-data.org/v4")
    comp = cfg.get("competition_code", "WC")
    date = match.get("date", "")
    url  = f"{base}/competitions/{comp}/matches?dateFrom={date}&dateTo={date}"
    req  = urllib.request.Request(url, headers={
        "X-Auth-Token": api_key,
        "User-Agent":   "LaAlbiceleste2026/1.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        t1 = match.get("team1", "").lower()
        t2 = match.get("team2", "").lower()
        for m in data.get("matches", []):
            hn = m.get("homeTeam", {}).get("name", "").lower()
            an = m.get("awayTeam", {}).get("name", "").lower()
            if (t1 in hn or hn in t1) and (t2 in an or an in t2):
                ft = m.get("score", {}).get("fullTime", {})
                if m.get("status") == "FINISHED" and ft.get("home") is not None:
                    return {"home": ft["home"], "away": ft["away"]}
    except Exception as exc:
        print(f"[results-api] {exc}")
    return None


# ── In-memory cache ──────────────────────────────────────────────────────────
_cache_lock = threading.Lock()
_cache = {"data": None, "fetched_at": 0}
_tz_cache_lock = threading.Lock()
_tz_cache = {}
_TZ_CACHE_TTL = 3600
_gs_guesses_all_cache_lock = threading.Lock()
_gs_guesses_all_cache = {"payload": None, "expires_at": 0}
_GS_GUESSES_ALL_CACHE_TTL = 15


def _invalidate_guesses_all_cache():
    with _gs_guesses_all_cache_lock:
        _gs_guesses_all_cache["payload"] = None
        _gs_guesses_all_cache["expires_at"] = 0


# ── SSL context (handles corporate/self-signed CA chains) ────────────────────
def _make_ssl_context():
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass  # fall back to the default CA bundle shipped with Python
    return ctx

_SSL_CTX = _make_ssl_context()


def _is_public_ip(ip_str):
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return not (
            ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local
            or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified
        )
    except ValueError:
        return False


def _extract_client_ip(handler):
    headers = (
        handler.headers.get("CF-Connecting-IP", ""),
        handler.headers.get("X-Real-IP", ""),
        handler.headers.get("X-Forwarded-For", ""),
    )

    for raw in headers:
        if not raw:
            continue
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        for candidate in parts:
            if _is_public_ip(candidate):
                return candidate
        if parts:
            return parts[0]

    remote = (handler.client_address or [""])[0]
    return remote or ""


def _fetch_ip_timezone(ip):
    if not ip or not _is_public_ip(ip):
        return None

    now = time.time()
    with _tz_cache_lock:
        cached = _tz_cache.get(ip)
        if cached and now - cached["at"] < _TZ_CACHE_TTL:
            return cached["data"]

    providers = (
        {
            "url": f"https://ipapi.co/{urllib.parse.quote(ip)}/json/",
            "parser": lambda d: {
                "timeZone": d.get("timezone"),
                "country": d.get("country_name"),
                "countryCode": d.get("country_code"),
            },
        },
        {
            "url": f"https://ipwho.is/{urllib.parse.quote(ip)}",
            "parser": lambda d: {
                "timeZone": (d.get("timezone") or {}).get("id"),
                "country": d.get("country"),
                "countryCode": d.get("country_code"),
            },
        },
    )

    for provider in providers:
        try:
            req = urllib.request.Request(provider["url"], headers={"User-Agent": "LaAlbiceleste2026/1.0"})
            with urllib.request.urlopen(req, timeout=4, context=_SSL_CTX) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            info = provider["parser"](payload)
            tz = info.get("timeZone")
            if tz:
                with _tz_cache_lock:
                    _tz_cache[ip] = {"at": now, "data": info}
                return info
        except Exception:
            continue

    return None


def fetch_bulletin(retries=3):
    with _cache_lock:
        now = time.time()
        if _cache["data"] is not None and now - _cache["fetched_at"] < CACHE_TTL:
            return _cache["data"], _cache["fetched_at"]

    req = urllib.request.Request(
        BULLETIN_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; SoccerAPIClone/1.0)",
        },
    )
    last_exc = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120, context=_SSL_CTX) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            break
        except http.client.IncompleteRead as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
        except Exception:
            raise
    else:
        raise last_exc

    with _cache_lock:
        _cache["data"] = raw
        _cache["fetched_at"] = time.time()
    return raw, _cache["fetched_at"]



# ── Parsers ──────────────────────────────────────────────────────────────────
def parse_events(raw):
    # Primary path: raw['sg']['EA']
    try:
        ea = raw["sg"]["EA"]
        if isinstance(ea, list):
            # Filter out grouping/category rows (negative TYPE or missing team names)
            return [e for e in ea if e.get("HN") or e.get("ENO")]
    except (KeyError, TypeError):
        pass

    # Fallback: bare list
    if isinstance(raw, list):
        return raw

    # Fallback: common wrapper keys
    for key in ("Value", "value", "data", "events", "items"):
        v = raw.get(key)
        if isinstance(v, list) and v:
            return v

    # Last resort: first list value found
    for v in raw.values():
        if isinstance(v, list) and v:
            return v
    return []




def _outcome_label(mtid, n, sov, on, lang="tr"):
    """Return the best human-readable label for a single bet outcome."""
    sov = sov or 0
    sov_s = f"{sov:g}" if sov else ""

    if lang == "tr":
        # 1. Use raw name from bulletin (already Turkish)
        if on:
            return on
        # 2. Over/Under — Turkish: n=1=Alt, n=2=Üst
        if mtid in _OU_MTIDS:
            if n == 1: return f"Alt {sov_s}" if sov_s else "Alt"
            if n == 2: return f"Üst {sov_s}" if sov_s else "Üst"
        # 3. Asian Handicap
        if mtid in _AH_MTIDS:
            if sov:
                home_tag = f"{sov:+g}"
                away_tag = f"{-sov:+g}"
                if n == 1: return f"1 ({home_tag})"
                if n == 2: return f"2 ({away_tag})"
            return {1: "1", 2: "2"}.get(n, f"Seçenek {n}")
        # 4. European Handicap
        if mtid in _EH_MTIDS:
            tag = f"{sov:+g}" if sov else "0"
            return {1: f"1 ({tag})", 2: f"X ({tag})", 3: f"2 ({tag})"}.get(n, f"Seçenek {n}")
        # 5. Static Turkish lookup
        return OUTCOME_LABELS_TR.get(mtid, {}).get(n, f"Seçenek {n}")

    else:  # lang == "en"
        # 1. Use the name from the API when available (translate short Turkish words)
        if on:
            return _TR_TO_EN.get(on, on)
        # 2. Over/Under markets — include the spread value
        # Nesine bulletin: n=1 = Under (Alt), n=2 = Over (Üst)
        if mtid in _OU_MTIDS:
            if n == 1: return f"Under {sov_s}" if sov_s else "Under"
            if n == 2: return f"Over {sov_s}" if sov_s else "Over"
        # 3. Asian Handicap 2-way — home tag = sov formatted with sign, away = negated
        if mtid in _AH_MTIDS:
            if sov:
                home_tag = f"{sov:+g}"   # e.g. "+3.5" or "-1.5"
                away_tag = f"{-sov:+g}"  # e.g. "-3.5" or "+1.5"
                if n == 1: return f"1 ({home_tag})"
                if n == 2: return f"2 ({away_tag})"
            return {1: "1", 2: "2"}.get(n, f"Option {n}")
        # 4. European Handicap 3-way — handicap displayed on each outcome
        if mtid in _EH_MTIDS:
            tag = f"{sov:+g}" if sov else "0"
            return {1: f"1 ({tag})", 2: f"X ({tag})", 3: f"2 ({tag})"}.get(n, f"Option {n}")
        # 5. Static lookup table
        return OUTCOME_LABELS.get(mtid, {}).get(n, f"Option {n}")


def _market_type_name(mtid, sov, mn, lang):
    if lang == "tr":
        base = MARKET_TYPE_NAMES_TR.get(mtid) or mn or f"Pazar #{mtid}"
    else:
        base = MARKET_TYPE_NAMES.get(mtid) or (_TR_TO_EN.get(mn, mn) if mn else None) or f"Market #{mtid}"
    if mtid in _EH_MTIDS and sov != 0:
        return f"{base} (0:{abs(sov):g})" if sov < 0 else f"{base} ({sov:g}:0)"
    if mtid in (798, 799) and sov != 0:
        spread = f"{abs(sov):g}"
        return f"{base} (0:{spread})" if sov < 0 else f"{base} ({spread}:0)"
    if mtid == 272 and sov != 0:
        sign = "+" if sov > 0 else ""
        return f"{base} ({sign}{sov:g})"
    return base


def format_market(market, lang="tr"):
    mtid = market.get("MTID", 0)
    sov  = market.get("SOV") or 0
    mn   = market.get("MN")
    outcomes = [
        {
            "n":       oc.get("N", 0),
            "label":   _outcome_label(mtid, oc.get("N", 0), sov, oc.get("ON"), lang),
            "labelTr": _outcome_label(mtid, oc.get("N", 0), sov, oc.get("ON"), "tr"),
            "labelEn": _outcome_label(mtid, oc.get("N", 0), sov, oc.get("ON"), "en"),
            "odds":    oc.get("O"),
            "no":      oc.get("NO"),
        }
        for oc in market.get("OCA", [])
    ]
    return {
        "id":          market.get("ID"),
        "no":          market.get("NO"),
        "typeId":      mtid,
        "typeName":    _market_type_name(mtid, sov, mn, lang),
        "typeNameTr":  _market_type_name(mtid, sov, mn, "tr"),
        "typeNameEn":  _market_type_name(mtid, sov, mn, "en"),
        "spreadValue": sov,
        "status":      market.get("MS"),
        "outcomes":    outcomes,
        "startDate":   market.get("MSD"),
        "endDate":     market.get("MED"),
        "isInPlay":    market.get("INM") == 1,
    }


def get_league_names(raw):
    """Build a league-code → name map from the bulletin's LA array.
    Config-defined names take priority over bulletin names."""
    names = {}
    try:
        for entry in raw.get("sg", {}).get("LA", []):
            lid = entry.get("LID")
            name = entry.get("N")
            if lid is not None and name:
                names[lid] = name
    except (TypeError, AttributeError):
        pass
    names.update(LEAGUE_NAMES)  # config always wins
    return names


def format_event(ev, lang="tr", league_names=None):
    if league_names is None:
        league_names = LEAGUE_NAMES
    sport_types_map = SPORT_TYPES_TR if lang == "tr" else SPORT_TYPES
    return {
        "id": ev.get("C"),
        "eventId": ev.get("EV"),
        "homeTeam":   ev.get("HN", ""),
        "awayTeam":   ev.get("AN", ""),
        "homeTeamEn": _team_en(ev.get("HN", "")),
        "awayTeamEn": _team_en(ev.get("AN", "")),
        "displayName": ev.get("ENO") or f"{ev.get('HN','')} - {ev.get('AN','')}",
        "sportType": ev.get("TYPE"),
        "sportName": sport_types_map.get(ev.get("TYPE", 0), f"Type {ev.get('TYPE')}"),
        "date": ev.get("D", ""),
        "day": ev.get("DAY", ""),
        "time": ev.get("T", ""),
        "startTimestamp": ev.get("ESD"),
        "status": _match_status(datetime.fromtimestamp(ev["ESD"] / 1000, tz=timezone.utc) if ev.get("ESD") else None),
        "leagueCode": ev.get("LC"),
        "leagueName": league_names.get(ev.get("LC"), f"League #{ev.get('LC')}"),
        "isLive": ev.get("LE") == 1,
        "markets": [format_market(m, lang) for m in ev.get("MA", []) if m.get("MTID") not in _KO_HIDDEN_TYPEIDS],
        "marketCount": sum(1 for m in ev.get("MA", []) if m.get("MTID") not in _KO_HIDDEN_TYPEIDS),
    }


# ── HTTP handler ─────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path):
        if not os.path.isfile(path):
            self.send_response(404)
            self.end_headers()
            return
        mime, _ = mimetypes.guess_type(path)
        mime = mime or "application/octet-stream"
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        if mime.startswith("text/html"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        elif mime in ("text/css", "application/javascript", "text/javascript"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            lang = qs.get("lang", ["tr"])[0].lower()
            if lang not in ("tr", "en"):
                lang = "tr"

            # ── /api/matches ───────────────────────────────────────────────
            if path == "/api/matches":
                raw, fetched_at = fetch_bulletin()
                events = parse_events(raw)

                _defaults = CONFIG.get("defaults", {})
                _def_sport = str(_defaults.get("sport", 1))
                _def_leagues = _defaults.get("leagues", [])
                _def_league_str = ",".join(str(c) for c in _def_leagues) if _def_leagues else "0"

                sport_filter = int(qs.get("sport", [_def_sport])[0])
                search = qs.get("search", [""])[0].lower().strip()
                date_filter = qs.get("date", [""])[0].strip()
                league_raw = qs.get("league", [_def_league_str])[0]
                league_filter = [] if (league_raw == "0" or not league_raw) else [
                    int(x) for x in league_raw.split(",") if x.strip().isdigit()
                ]

                filtered = events
                if sport_filter != 0:
                    filtered = [e for e in filtered if e.get("TYPE") == sport_filter]

                # Build league list from sport-filtered events (before league filter)
                league_names = get_league_names(raw)
                lc_counts = {}
                for e in filtered:
                    lc = e.get("LC")
                    if lc is not None:
                        lc_counts[lc] = lc_counts.get(lc, 0) + 1
                leagues_list = [
                    {"code": lc, "name": league_names.get(lc, f"League #{lc}"), "count": cnt}
                    for lc, cnt in sorted(lc_counts.items(), key=lambda x: -x[1])
                ]

                if league_filter:
                    filtered = [e for e in filtered if e.get("LC") in league_filter]
                if search:
                    filtered = [
                        e for e in filtered
                        if search in (e.get("HN") or "").lower()
                        or search in (e.get("AN") or "").lower()
                        or search in (e.get("ENO") or "").lower()
                    ]
                if date_filter:
                    filtered = [e for e in filtered if e.get("D") == date_filter]

                # Build sport-type summary from ALL EA events (including group rows)
                try:
                    all_ea = raw["sg"]["EA"]
                except (KeyError, TypeError):
                    all_ea = events

                type_counts = {}
                for e in all_ea:
                    t = e.get("TYPE")
                    if isinstance(t, int) and t > 0 and (e.get("HN") or e.get("ENO")):
                        type_counts[t] = type_counts.get(t, 0) + 1

                sport_types_map = SPORT_TYPES_TR if lang == "tr" else SPORT_TYPES
                sport_types_list = [
                    {"id": t, "name": sport_types_map.get(t, f"Type {t}"), "count": c}
                    for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
                ]

                matches_formatted = [format_event(e, lang, league_names) for e in filtered]

                # Keep the knockout match log up-to-date for credit penalty tracking
                if sport_filter == 1 and not search:
                    wc_matches = [m for m in matches_formatted if m.get("leagueCode") == 10151]
                    if wc_matches:
                        threading.Thread(
                            target=_ko_update_match_log,
                            args=(wc_matches,),
                            daemon=True,
                        ).start()
                    threading.Thread(target=_ko_maybe_settle, daemon=True).start()

                self.send_json(200, {
                    "total": len(filtered),
                    "cacheAge": int(time.time() - fetched_at),
                    "sportTypes": sport_types_list,
                    "leagues": leagues_list,
                    "activeLeagues": league_filter,
                    "matches": matches_formatted,
                })
                return

            # ── /api/matches/<id> ──────────────────────────────────────────
            if path.startswith("/api/matches/"):
                match_id = path[len("/api/matches/"):]
                raw, _ = fetch_bulletin()
                events = parse_events(raw)
                ev = next((e for e in events if str(e.get("C")) == match_id), None)
                if ev is None:
                    self.send_json(404, {"error": "Match not found"})
                else:
                    self.send_json(200, format_event(ev, lang, get_league_names(raw)))
                return

            # ── /api/markets/<mtid> ────────────────────────────────────────
            if path.startswith("/api/markets/"):
                mtid = int(path[len("/api/markets/"):])
                raw, _ = fetch_bulletin()
                events = parse_events(raw)
                results = []
                for ev in events:
                    if ev.get("TYPE") != 1:
                        continue
                    for m in ev.get("MA", []):
                        if m.get("MTID") == mtid:
                            entry = format_market(m, lang)
                            entry["match"] = f"{ev.get('HN','')} - {ev.get('AN','')}"
                            entry["matchId"] = ev.get("C")
                            entry["date"] = ev.get("D", "")
                            entry["time"] = ev.get("T", "")
                            results.append(entry)
                market_type_name = MARKET_TYPE_NAMES.get(mtid, f"Market #{mtid}")
                self.send_json(200, {
                    "marketTypeName": market_type_name,
                    "count": len(results),
                    "markets": results,
                })
                return

            # ── /api/config ───────────────────────────────────────────────
            if path == "/api/config":
                self.send_json(200, load_config())
                return

            # ── /api/user/avatar/<username> ───────────────────────────────
            if path.startswith("/api/user/avatar/"):
                uname = path[len("/api/user/avatar/"):]
                users_data = _jload(_USERS_FILE, {"users": {}})
                logo = users_data.get("users", {}).get(uname, {}).get("logoData")
                if logo and isinstance(logo, str) and logo.startswith("data:image/") and "," in logo:
                    header, b64 = logo.split(",", 1)
                    mime = header.split(";")[0].replace("data:", "") or "image/png"
                    import base64 as _b64
                    img_bytes = _b64.b64decode(b64)
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(len(img_bytes)))
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.end_headers()
                    self.wfile.write(img_bytes)
                else:
                    self.send_response(404)
                    self.end_headers()
                return

            # ── /api/client-context ───────────────────────────────────────
            if path == "/api/client-context":
                client_ip = _extract_client_ip(self)
                tz_info = _fetch_ip_timezone(client_ip) or {}
                self.send_json(200, {
                    "ip": client_ip,
                    "timeZone": tz_info.get("timeZone"),
                    "country": tz_info.get("country"),
                    "countryCode": tz_info.get("countryCode"),
                })
                return

            # ── /api/stage/redirect-target ───────────────────────────────
            if path == "/api/stage/redirect-target":
                self.send_json(200, {
                    "stage": _active_stage_name(),
                    "target": _active_stage_target(),
                    "groupStageFinished": _is_group_stage_finished(),
                    "config": {
                        "groupStagePath": _GROUP_STAGE_PATH,
                        "knockoutStagePath": _KNOCKOUT_STAGE_PATH,
                        "forceStage": STAGE_REDIRECT_CFG.get("force_stage", ""),
                    },
                })
                return

            # ── /api/raw ───────────────────────────────────────────────────
            if path == "/api/raw":
                raw, _ = fetch_bulletin()
                self.send_json(200, raw)
                return
            # ── /api/knockout/bets ────────────────────────────────────────
            if path == "/api/knockout/bets":
                token    = qs.get("token", [""])[0]
                username = _validate_token(token)
                if not username:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                threading.Thread(target=_ko_maybe_settle, daemon=True).start()
                bets   = _jload(_KO_BETS_FILE, {"bets": {}}).get("bets", {}).get(username, {})
                credit = _ko_compute_credit(username)
                # Enrich bets with match names from log if not already stored on the bet
                log_matches = _jload(_KO_MATCH_LOG_FILE, {"matches": {}}).get("matches", {})
                enriched_bets = {}
                for mid, bet in bets.items():
                    bet = dict(bet)
                    if not bet.get("matchName"):
                        minfo = log_matches.get(mid, {})
                        bet["matchName"]   = minfo.get("name", mid)
                        bet["matchNameEn"] = _match_name_en(minfo, mid)
                    enriched_bets[mid] = bet
                self.send_json(200, {
                    "bets":       enriched_bets,
                    "credit":     credit,
                    "creditBase": KNOCKOUT_CREDIT_BASE,
                    "minBet":     KNOCKOUT_MIN_BET,
                    "maxBet":     KNOCKOUT_MAX_BET,
                })
                return


            # ── /api/knockout/leaderboard ─────────────────────────────────
            if path == "/api/knockout/leaderboard":
                self.send_json(200, {"leaderboard": _ko_compute_leaderboard()})
                return

            # ── /api/knockout/bets/all ────────────────────────────────────
            if path == "/api/knockout/bets/all":
                now_ts     = time.time()
                log        = _jload(_KO_MATCH_LOG_FILE, {"matches": {}})
                bets_data  = _jload(_KO_BETS_FILE, {"bets": {}})
                users_data = _jload(_USERS_FILE, {"users": {}})
                res_data   = _jload(_KO_RESULTS_FILE, {"results": {}}).get("results", {})
                out = {}
                for match_id, minfo in log["matches"].items():
                    ts = minfo.get("startTimestamp")
                    if not ts:
                        continue
                    ts_f   = float(ts)
                    ts_sec = ts_f / 1000.0 if ts_f > 1e10 else ts_f
                    if ts_sec > now_ts:
                        continue
                    match_bets = []
                    for uname, user_bets in bets_data.get("bets", {}).items():
                        bet = user_bets.get(match_id)
                        if not bet:
                            continue
                        uinfo = users_data.get("users", {}).get(uname, {})
                        _tid  = bet.get("typeId") or 0
                        _sov  = bet.get("spreadValue") or 0
                        _n    = bet.get("outcomeN") or 0
                        _mn   = bet.get("marketName") or ""
                        match_bets.append({
                            "username":        uname,
                            "displayName":     uinfo.get("displayName", uname),
                            "supportedTeam":   uinfo.get("supportedTeam"),
                            "hasLogo":         bool(uinfo.get("logoData")),
                            "marketName":      bet.get("marketName"),
                            "marketNameTr":    _market_type_name(_tid, _sov, _mn, "tr"),
                            "marketNameEn":    _market_type_name(_tid, _sov, _mn, "en"),
                            "typeId":          _tid,
                            "spreadValue":     _sov,
                            "outcomeN":        _n,
                            "outcomeLabel":    bet.get("outcomeLabel"),
                            "outcomeLabelTr":  _outcome_label(_tid, _n, _sov, bet.get("outcomeLabel"), "tr"),
                            "outcomeLabelEn":  _outcome_label(_tid, _n, _sov, bet.get("outcomeLabelEn") or bet.get("outcomeLabel"), "en"),
                            "odds":            bet.get("odds"),
                            "amount":          bet.get("amount"),
                            "won":             bet.get("won"),
                            "payout":          bet.get("payout"),
                            "settledAt":       bet.get("settledAt"),
                            "resultDetail":    _ko_bet_result_detail(bet, res_data.get(match_id)),
                        })
                    # Build compact result summary for this match
                    r = res_data.get(match_id, {})
                    def _names(lst, key="player", filt=None):
                        return [g.get(key, "") for g in lst
                                if g.get(key) and (filt is None or filt(g))]
                    gs = r.get("goalScorers", [])
                    ce = r.get("cardEvents", [])
                    match_result = None
                    if r.get("homeGoals") is not None:
                        match_result = {
                            "home":    r.get("homeGoals"),
                            "away":    r.get("awayGoals"),
                            "htHome":  r.get("htHomeGoals"),
                            "htAway":  r.get("htAwayGoals"),
                            "status":  r.get("status", "FT"),
                            "scorers":       _names(gs, filt=lambda g: not g.get("isOwnGoal")),
                            "assisters":     _names(gs, key="assist", filt=lambda g: not g.get("isOwnGoal") and g.get("assist")),
                            "firstScorer":   next((_names(gs, filt=lambda g: not g.get("isOwnGoal")) or [None]).__iter__(), None),
                            "headerScorers": _names(gs, filt=lambda g: g.get("detail") == "goal---header"),
                            "fkScorers":     _names(gs, filt=lambda g: g.get("detail") == "goal---free-kick"),
                            "yellowCards":   _names(ce, filt=lambda c: c.get("type") == "yellow"),
                            "redCards":      _names(ce, filt=lambda c: c.get("type") == "red"),
                            "anyCards":      _names(ce),
                            "statistics":      r.get("statistics"),
                            "h1Corners":       r.get("h1Corners"),
                            "firstCornerTeam": r.get("firstCornerTeam"),
                        }
                    out[match_id] = {
                        "name":           minfo.get("name", ""),
                        "nameEn":         _match_name_en(minfo),
                        "startTimestamp": minfo.get("startTimestamp"),
                        "result":         match_result,
                        "bets":           match_bets,
                    }
                self.send_json(200, {"matches": out})
                return

            # ── /api/knockout/results ─────────────────────────────────────
            if path == "/api/knockout/results":
                results = _jload(_KO_RESULTS_FILE, {"results": {}})
                self.send_json(200, {"results": results.get("results", {})})
                return

            # ── /api/auth/* ────────────────────────────────────────────────
            if path == "/api/auth/me":
                token    = qs.get("token", [""])[0]
                username = _validate_token(token)
                if not username:
                    self.send_json(401, {"error": "Not authenticated"})
                    return
                users = _jload(_USERS_FILE, {"users": {}})
                user  = users.get("users", {}).get(username, {})
                self.send_json(200, {
                    "username":    username,
                    "displayName": user.get("displayName", username),
                    "isAdmin":     user.get("isAdmin", False),
                    "supportedTeam": user.get("supportedTeam"),
                    "logoData": user.get("logoData"),
                })
                return

            # ── /api/groupstage/matches ────────────────────────────────────
            if path == "/api/groupstage/matches":
                enriched = []
                bonus_idx = 0
                for i, m in enumerate(_ALL_MATCHES):
                    if "group" not in m:
                        continue
                    enriched.append(_enrich_match(i, m, bonus_idx=bonus_idx))
                    bonus_idx += 1
                self.send_json(200, {"matches": enriched, "points": POINTS_CFG})
                return

            # ── /api/groupstage/squads ─────────────────────────────────────
            if path == "/api/groupstage/squads":
                self.send_json(200, {"squads": _SQUAD_LOOKUP})
                return

            # ── /api/groupstage/guesses ────────────────────────────────────
            if path == "/api/groupstage/guesses":
                token    = qs.get("token", [""])[0]
                username = _validate_token(token)
                if not username:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                gdata = _jload(_GUESS_FILE, {"guesses": {}})
                self.send_json(200, {
                    "guesses": gdata.get("guesses", {}).get(username, {})
                })
                return

            # ── /api/groupstage/guesses/all ────────────────────────────────
            if path == "/api/groupstage/guesses/all":
                now_ts = time.time()
                with _gs_guesses_all_cache_lock:
                    if _gs_guesses_all_cache["payload"] is not None and now_ts < _gs_guesses_all_cache["expires_at"]:
                        self.send_json(200, _gs_guesses_all_cache["payload"])
                        return

                gdata = _jload(_GUESS_FILE, {"guesses": {}})
                udata = _jload(_USERS_FILE, {"users": {}})
                rdata = _jload(_RES_FILE,   {"results": {}})

                matches_out = {}
                for idx, m in enumerate(_ALL_MATCHES):
                    if "group" not in m:
                        continue
                    
                    ko = _parse_kickoff_utc(m.get("date", ""), m.get("time", ""))
                    status = _match_status(ko)
                    if status == "upcoming":
                        continue

                    idx_s = str(idx)
                    res_entry = rdata.get("results", {}).get(idx_s, {})
                    res_score = res_entry.get("score")
                    fh_ans = res_entry.get("fhBonusAnswer")
                    sh_ans = res_entry.get("shBonusAnswer")

                    guesses_list = []
                    for uname, user_guesses in gdata.get("guesses", {}).items():
                        g = user_guesses.get(idx_s)
                        if not g:
                            continue
                        user_info = udata.get("users", {}).get(uname, {})
                        display = user_info.get("displayName", uname)
                        pts = None
                        if res_score:
                            pts = _calc_points(g, res_score, fh_ans, sh_ans)
                        guesses_list.append({
                            "username": uname,
                            "displayName": display,
                            "supportedTeam": user_info.get("supportedTeam"),
                            "homeScore": g.get("homeScore"),
                            "awayScore": g.get("awayScore"),
                            "fhBonus": g.get("fhBonus"),
                            "shBonus": g.get("shBonus"),
                            "points": pts,
                        })

                    matches_out[idx_s] = {
                        "status": status,
                        "result": res_score,
                        "fhBonusAnswer": fh_ans,
                        "shBonusAnswer": sh_ans,
                        "guesses": guesses_list,
                    }

                payload = {"matches": matches_out}
                with _gs_guesses_all_cache_lock:
                    _gs_guesses_all_cache["payload"] = payload
                    _gs_guesses_all_cache["expires_at"] = time.time() + _GS_GUESSES_ALL_CACHE_TTL

                self.send_json(200, payload)
                return

            # ── /api/groupstage/results ────────────────────────────────────
            if path == "/api/groupstage/results":
                token    = qs.get("token", [""])[0]
                username = _validate_token(token)
                rdata    = _jload(_RES_FILE, {"results": {}})
                if username and _is_admin(username):
                    self.send_json(200, rdata)
                else:
                    pub = {
                        k: {
                            "score": v.get("score"),
                            "scored": v.get("scored", False),
                            "fhBonusAnswer": v.get("fhBonusAnswer") if v.get("scored") else None,
                            "shBonusAnswer": v.get("shBonusAnswer") if v.get("scored") else None,
                        }
                        for k, v in rdata.get("results", {}).items()
                    }
                    self.send_json(200, {"results": pub})
                return

            # ── /api/groupstage/leaderboard ────────────────────────────────
            if path == "/api/groupstage/leaderboard":
                self.send_json(200, {"leaderboard": _compute_leaderboard()})
                return
            # ── Static files ───────────────────────────────────────────────
            if path == "/":
                self.send_file(os.path.join(PUBLIC_DIR, "index.html"))
            else:
                # Prevent directory traversal
                rel = os.path.normpath(path.lstrip("/"))
                if rel.startswith(".."):
                    self.send_response(403)
                    self.end_headers()
                    return
                self.send_file(os.path.join(PUBLIC_DIR, rel))

        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.send_json(500, {"error": str(exc)})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path.rstrip("/") or "/"
        cl     = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(cl) if cl else b""
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = {}
        try:
            # ── /api/auth/register ─────────────────────────────────────────
            if path == "/api/auth/register":
                uname   = (data.get("username") or "").strip().lower()
                pw      = data.get("password") or ""
                display = (data.get("displayName") or uname).strip()
                supported_team = (data.get("supportedTeam") or "").strip()
                logo_data = data.get("logoData")
                if not uname or not pw:
                    self.send_json(400, {"error": "Username and password required"})
                    return
                if not (3 <= len(uname) <= 30):
                    self.send_json(400, {"error": "Username: 3–30 characters"})
                    return
                if not re.match(r'^[a-z0-9_]+$', uname):
                    self.send_json(400, {"error": "Username: lowercase letters, digits, underscores only"})
                    return
                if supported_team and supported_team not in _SUPPORTED_TEAMS:
                    self.send_json(400, {"error": "Invalid supported team"})
                    return
                try:
                    logo_data = _validate_logo_data(logo_data)
                except ValueError as exc:
                    self.send_json(400, {"error": str(exc)})
                    return
                except OverflowError as exc:
                    self.send_json(400, {"error": str(exc)})
                    return
                with _data_lock:
                    users = _jload(_USERS_FILE, {"users": {}})
                    if uname in users.get("users", {}):
                        self.send_json(409, {"error": "Username already taken"})
                        return
                    users.setdefault("users", {})[uname] = {
                        "displayName": display,
                        "password":    _hash_pw(pw),
                        "isAdmin":     False,
                        "supportedTeam": supported_team or None,
                        "logoData":     logo_data or None,
                        "createdAt":   datetime.now(timezone.utc).isoformat(),
                    }
                    _jsave(_USERS_FILE, users)
                token = _create_token(uname)
                self.send_json(201, {"token": token, "username": uname,
                                     "displayName": display, "isAdmin": False,
                                     "supportedTeam": supported_team or None,
                                     "logoData": logo_data or None})
                return

            # ── /api/auth/login ────────────────────────────────────────────
            if path == "/api/auth/login":
                uname = (data.get("username") or "").strip().lower()
                pw    = data.get("password") or ""
                users = _jload(_USERS_FILE, {"users": {}})
                user  = users.get("users", {}).get(uname)
                if not user or user.get("password") != _hash_pw(pw):
                    self.send_json(401, {"error": "Invalid username or password"})
                    return
                token = _create_token(uname)
                self.send_json(200, {
                    "token":       token,
                    "username":    uname,
                    "displayName": user.get("displayName", uname),
                    "isAdmin":     user.get("isAdmin", False),
                    "supportedTeam": user.get("supportedTeam"),
                    "logoData": user.get("logoData"),
                })
                return

            # ── /api/auth/profile ─────────────────────────────────────────
            if path == "/api/auth/profile":
                token = data.get("token") or ""
                username = _validate_token(token)
                current_pw = data.get("currentPassword") or ""
                new_pw = data.get("newPassword") or ""
                supported_team = data.get("supportedTeam")
                logo_data = data.get("logoData")
                if not username:
                    self.send_json(401, {"error": "Not authenticated"})
                    return
                if not current_pw:
                    self.send_json(400, {"error": "Current password required"})
                    return
                if supported_team is not None:
                    supported_team = (supported_team or "").strip()
                    if supported_team and supported_team not in _SUPPORTED_TEAMS:
                        self.send_json(400, {"error": "Invalid supported team"})
                        return
                try:
                    logo_data = _validate_logo_data(logo_data)
                except ValueError as exc:
                    self.send_json(400, {"error": str(exc)})
                    return
                except OverflowError as exc:
                    self.send_json(400, {"error": str(exc)})
                    return

                with _data_lock:
                    users = _jload(_USERS_FILE, {"users": {}})
                    user = users.get("users", {}).get(username)
                    if not user or user.get("password") != _hash_pw(current_pw):
                        self.send_json(401, {"error": "Incorrect current password"})
                        return
                    if supported_team is not None:
                        user["supportedTeam"] = supported_team or None
                    if logo_data is not None:
                        user["logoData"] = logo_data or None
                    if new_pw:
                        user["password"] = _hash_pw(new_pw)
                    _jsave(_USERS_FILE, users)

                response_token = token
                if new_pw:
                    _invalidate_user_tokens(username)
                    response_token = _create_token(username)

                fresh = users.get("users", {}).get(username, {})
                response = {
                    "token": response_token,
                    "username": username,
                    "displayName": fresh.get("displayName", username),
                    "isAdmin": fresh.get("isAdmin", False),
                    "supportedTeam": fresh.get("supportedTeam"),
                    "logoData": fresh.get("logoData"),
                }
                self.send_json(200, response)
                return

            # ── /api/auth/logout ───────────────────────────────────────────
            if path == "/api/auth/logout":
                token = data.get("token") or ""
                with _data_lock:
                    _tokens.pop(token, None)
                self.send_json(200, {"ok": True})
                return

            # ── /api/groupstage/guess ──────────────────────────────────────
            if path == "/api/groupstage/guess":
                token    = data.get("token") or ""
                username = _validate_token(token)
                if not username:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                idx = data.get("matchIndex")
                if idx is None or not isinstance(idx, int):
                    self.send_json(400, {"error": "matchIndex required (int)"})
                    return
                if not (0 <= idx < len(_ALL_MATCHES)):
                    self.send_json(400, {"error": "Invalid matchIndex"})
                    return
                m  = _ALL_MATCHES[idx]
                ko = _parse_kickoff_utc(m.get("date", ""), m.get("time", ""))
                if ko and datetime.now(timezone.utc) >= ko:
                    self.send_json(403, {"error": "Match has already started – no changes allowed"})
                    return
                try:
                    hs = int(data["homeScore"])
                    as_ = int(data["awayScore"])
                    if not (0 <= hs <= 30 and 0 <= as_ <= 30):
                        raise ValueError()
                except (KeyError, ValueError, TypeError):
                    self.send_json(400, {"error": "homeScore and awayScore must be integers 0–30"})
                    return
                guess = {
                    "homeScore": hs, "awayScore": as_,
                    "fhBonus":   data.get("fhBonus"),
                    "shBonus":   data.get("shBonus"),
                    "savedAt":   datetime.now(timezone.utc).isoformat(),
                }
                with _data_lock:
                    gdata = _jload(_GUESS_FILE, {"guesses": {}})
                    gdata.setdefault("guesses", {}).setdefault(username, {})[str(idx)] = guess
                    _jsave(_GUESS_FILE, gdata)
                _invalidate_guesses_all_cache()
                self.send_json(200, {"ok": True, "guess": guess})
                return

            # ── /api/groupstage/result  (admin: set result + bonus answers) ─
            if path == "/api/groupstage/result":
                token    = data.get("token") or ""
                username = _validate_token(token)
                if not username or not _is_admin(username):
                    self.send_json(403, {"error": "Admin access required"})
                    return
                idx = data.get("matchIndex")
                hs  = data.get("homeScore")
                as_ = data.get("awayScore")
                if None in (idx, hs, as_):
                    self.send_json(400, {"error": "matchIndex, homeScore, awayScore required"})
                    return
                with _data_lock:
                    rdata = _jload(_RES_FILE, {"results": {}})
                    rdata.setdefault("results", {})[str(idx)] = {
                        "score":        {"home": int(hs), "away": int(as_)},
                        "fhBonusAnswer": data.get("fhBonusAnswer"),
                        "shBonusAnswer": data.get("shBonusAnswer"),
                        "scored":        True,
                        "enteredAt":     datetime.now(timezone.utc).isoformat(),
                    }
                    _jsave(_RES_FILE, rdata)
                _invalidate_guesses_all_cache()
                self.send_json(200, {"ok": True, "leaderboard": _compute_leaderboard()})
                return

            # ── /api/groupstage/result/clear  (admin: delete a result) ─
            if path == "/api/groupstage/result/clear":
                token    = data.get("token") or ""
                username = _validate_token(token)
                if not username or not _is_admin(username):
                    self.send_json(403, {"error": "Admin access required"})
                    return
                idx = data.get("matchIndex")
                if idx is None:
                    self.send_json(400, {"error": "matchIndex required"})
                    return
                with _data_lock:
                    rdata = _jload(_RES_FILE, {"results": {}})
                    rdata.setdefault("results", {}).pop(str(idx), None)
                    _jsave(_RES_FILE, rdata)
                _invalidate_guesses_all_cache()
                self.send_json(200, {"ok": True})
                return

            # ── /api/groupstage/score  (admin: auto-fetch result from API) ─
            if path == "/api/groupstage/score":
                token    = data.get("token") or ""
                username = _validate_token(token)
                if not username or not _is_admin(username):
                    self.send_json(403, {"error": "Admin access required"})
                    return
                idx = data.get("matchIndex")
                if idx is None or not (0 <= int(idx) < len(_ALL_MATCHES)):
                    self.send_json(400, {"error": "Invalid matchIndex"})
                    return
                match  = _ALL_MATCHES[int(idx)]
                result = _fetch_result_api(match)
                if not result:
                    self.send_json(503, {"error": (
                        "Could not fetch result from API. "
                        "Configure results_api.api_key in config.json or use /api/groupstage/result."
                    )})
                    return
                with _data_lock:
                    rdata = _jload(_RES_FILE, {"results": {}})
                    existing = rdata.setdefault("results", {}).get(str(idx), {})
                    existing.update({"score": result, "scored": True,
                                     "fetchedAt": datetime.now(timezone.utc).isoformat()})
                    rdata["results"][str(idx)] = existing
                    _jsave(_RES_FILE, rdata)
                _invalidate_guesses_all_cache()
                self.send_json(200, {"ok": True, "result": result,
                                     "leaderboard": _compute_leaderboard()})
                return

            # ── /api/knockout/bet/delete ──────────────────────────────────
            if path == "/api/knockout/bet/delete":
                token    = data.get("token") or ""
                username = _validate_token(token)
                if not username:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                match_id = str(data.get("matchId") or "").strip()
                if not match_id:
                    self.send_json(400, {"error": "matchId required"})
                    return
                with _data_lock:
                    bets_data = _jload(_KO_BETS_FILE, {"bets": {}})
                    user_bets = bets_data.get("bets", {}).get(username, {})
                    bet = user_bets.get(match_id)
                    if not bet:
                        self.send_json(404, {"error": "Bet not found"})
                        return
                    start_ts = bet.get("startTimestamp")
                    if start_ts is not None:
                        try:
                            ts_f   = float(start_ts)
                            ts_sec = ts_f / 1000.0 if ts_f > 1e10 else ts_f
                            if time.time() >= ts_sec:
                                self.send_json(403, {"error": "Match has already started – cannot delete bet"})
                                return
                        except (ValueError, TypeError):
                            pass
                    user_bets.pop(match_id, None)
                    _jsave(_KO_BETS_FILE, bets_data)
                credit = _ko_compute_credit(username)
                self.send_json(200, {"ok": True, "credit": credit})
                return

            # ── /api/knockout/bet ─────────────────────────────────────────
            if path == "/api/knockout/bet":
                token    = data.get("token") or ""
                username = _validate_token(token)
                if not username:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                match_id       = str(data.get("matchId") or "").strip()
                match_name     = str(data.get("matchName") or "").strip()
                match_name_en  = str(data.get("matchNameEn") or "").strip()
                start_ts       = data.get("startTimestamp")
                market_id        = str(data.get("marketId") or "").strip()
                market_name      = str(data.get("marketName") or "").strip()
                market_name_en   = str(data.get("marketNameEn") or "").strip()
                outcome_label    = str(data.get("outcomeLabel") or "").strip()
                outcome_label_en = str(data.get("outcomeLabelEn") or "").strip()
                odds          = data.get("odds")
                amount_raw    = data.get("amount")
                if not match_id or not outcome_label or odds is None:
                    self.send_json(400, {"error": "matchId, outcomeLabel, and odds are required"})
                    return
                try:
                    odds = float(odds)
                    if odds <= 0:
                        raise ValueError
                except (ValueError, TypeError):
                    self.send_json(400, {"error": "odds must be a positive number"})
                    return
                credit_now = _ko_compute_credit(username)
                dynamic_max = max(KNOCKOUT_MIN_BET, int(credit_now * 0.20))
                try:
                    amount = int(amount_raw) if amount_raw is not None else KNOCKOUT_MIN_BET
                    if not (KNOCKOUT_MIN_BET <= amount <= dynamic_max):
                        raise ValueError
                except (ValueError, TypeError):
                    self.send_json(400, {"error": f"Bet amount must be between {KNOCKOUT_MIN_BET} and {dynamic_max}"})
                    return
                if start_ts is not None:
                    try:
                        ts_f   = float(start_ts)
                        ts_sec = ts_f / 1000.0 if ts_f > 1e10 else ts_f
                        if time.time() >= ts_sec:
                            self.send_json(403, {"error": "Match has already started – betting is closed"})
                            return
                    except (ValueError, TypeError):
                        pass
                # Check the user has enough credit (refund old bet amount first)
                current_credit = _ko_compute_credit(username)
                with _data_lock:
                    bets_data = _jload(_KO_BETS_FILE, {"bets": {}})
                    old_bet   = bets_data.get("bets", {}).get(username, {}).get(match_id, {})
                old_amount = float(old_bet.get("amount", 0)) if old_bet else 0
                if current_credit + old_amount - amount < 0:
                    self.send_json(400, {"error": "Insufficient credits"})
                    return
                try:
                    outcome_n    = int(data.get("outcomeN") or 0)
                    type_id      = int(data.get("typeId") or 0)
                    spread_value = float(data.get("spreadValue") or 0)
                except (ValueError, TypeError):
                    outcome_n = type_id = 0
                    spread_value = 0.0

                bet = {
                    "matchName":   match_name,
                    "matchNameEn": match_name_en or match_name,
                    "marketId":       market_id,
                    "marketName":     market_name,
                    "marketNameEn":   market_name_en or market_name,
                    "outcomeLabel":   outcome_label,
                    "outcomeLabelEn": outcome_label_en or outcome_label,
                    "outcomeN":       outcome_n,
                    "typeId":         type_id,
                    "spreadValue":    spread_value,
                    "odds":           odds,
                    "amount":         amount,
                    "startTimestamp": start_ts,
                    "savedAt":        datetime.now(timezone.utc).isoformat(),
                }
                with _data_lock:
                    bets_data = _jload(_KO_BETS_FILE, {"bets": {}})
                    bets_data.setdefault("bets", {}).setdefault(username, {})[match_id] = bet
                    _jsave(_KO_BETS_FILE, bets_data)
                    log = _jload(_KO_MATCH_LOG_FILE, {"matches": {}})
                    if match_id not in log["matches"]:
                        log["matches"][match_id] = {
                            "name":           match_name,
                            "nameEn":         match_name_en or match_name,
                            "startTimestamp": start_ts,
                            "firstSeenAt":    datetime.now(timezone.utc).isoformat(),
                        }
                        _jsave(_KO_MATCH_LOG_FILE, log)
                credit = _ko_compute_credit(username)
                self.send_json(200, {"ok": True, "bet": bet, "credit": credit})
                return

            # ── /api/knockout/admin/fetch-results  (admin: trigger ESPN fetch) ─
            if path == "/api/knockout/admin/fetch-results":
                token    = data.get("token") or ""
                username = _validate_token(token)
                if not username or not _is_admin(username):
                    self.send_json(403, {"error": "Admin access required"})
                    return
                fetched  = []
                settled  = []
                log      = _jload(_KO_MATCH_LOG_FILE, {"matches": {}})
                res_data = _jload(_KO_RESULTS_FILE,   {"results": {}})
                now_ts   = time.time()
                for match_id, minfo in log.get("matches", {}).items():
                    ts = minfo.get("startTimestamp")
                    if not ts:
                        continue
                    ts_f   = float(ts)
                    ts_sec = ts_f / 1000.0 if ts_f > 1e10 else ts_f
                    if ts_sec > now_ts:
                        continue   # not started yet
                    if match_id in res_data.get("results", {}):
                        continue   # already have result
                    result = _ko_fetch_match_result_for_log_entry(minfo)
                    if not result:
                        continue
                    fetched.append(match_id)
                    with _data_lock:
                        rd = _jload(_KO_RESULTS_FILE, {"results": {}})
                        if match_id not in rd.get("results", {}):
                            rd.setdefault("results", {})[match_id] = {
                                **result,
                                "matchName": minfo.get("name", match_id),
                                "fetchedAt": datetime.now(timezone.utc).isoformat(),
                            }
                            _jsave(_KO_RESULTS_FILE, rd)
                    _ko_settle_match_bets(match_id, result)
                    settled.append(match_id)
                self.send_json(200, {
                    "ok":      True,
                    "fetched": fetched,
                    "settled": settled,
                })
                return

            # ── /api/knockout/admin/export-gs-credits  (admin: copy GS points → KO starting credits) ─
            if path == "/api/knockout/admin/export-gs-credits":
                token    = data.get("token") or ""
                username = _validate_token(token)
                if not username or not _is_admin(username):
                    self.send_json(403, {"error": "Admin access required"})
                    return
                lb = _compute_leaderboard()
                exported = {}
                with _data_lock:
                    users_data = _jload(_USERS_FILE, {"users": {}})
                    for entry in lb:
                        uname = entry["username"]
                        if uname not in users_data.get("users", {}):
                            continue
                        pts = entry["totalPoints"]
                        users_data["users"][uname]["koStartingCredit"] = pts
                        exported[uname] = pts
                    _jsave(_USERS_FILE, users_data)
                self.send_json(200, {"ok": True, "exported": exported})
                return

            # ── /api/knockout/admin/result  (admin: set or clear a KO result) ─
            if path == "/api/knockout/admin/result":
                token    = data.get("token") or ""
                username = _validate_token(token)
                if not username or not _is_admin(username):
                    self.send_json(403, {"error": "Admin access required"})
                    return
                match_id = str(data.get("matchId") or "").strip()
                if not match_id:
                    self.send_json(400, {"error": "matchId required"})
                    return
                # Clear mode
                if data.get("clear"):
                    with _data_lock:
                        res_data = _jload(_KO_RESULTS_FILE, {"results": {}})
                        res_data.setdefault("results", {}).pop(match_id, None)
                        _jsave(_KO_RESULTS_FILE, res_data)
                        # Also un-settle bets for this match
                        bets_data = _jload(_KO_BETS_FILE, {"bets": {}})
                        for ub in bets_data.get("bets", {}).values():
                            b = ub.get(match_id)
                            if b:
                                b.pop("won", None); b.pop("payout", None); b.pop("settledAt", None)
                        _jsave(_KO_BETS_FILE, bets_data)
                    self.send_json(200, {"ok": True, "cleared": match_id})
                    return
                # Set result
                try:
                    h    = int(data["homeGoals"])
                    a    = int(data["awayGoals"])
                    ht_h = data.get("htHomeGoals")
                    ht_a = data.get("htAwayGoals")
                    if ht_h is not None: ht_h = int(ht_h)
                    if ht_a is not None: ht_a = int(ht_a)
                except (KeyError, ValueError, TypeError):
                    self.send_json(400, {"error": "homeGoals and awayGoals (int) required"})
                    return
                result = {
                    "homeGoals":   h, "awayGoals":   a,
                    "htHomeGoals": ht_h, "htAwayGoals": ht_a,
                    "status":      data.get("status", "FT"),
                }
                with _data_lock:
                    res_data = _jload(_KO_RESULTS_FILE, {"results": {}})
                    log      = _jload(_KO_MATCH_LOG_FILE, {"matches": {}})
                    res_data.setdefault("results", {})[match_id] = {
                        **result,
                        "matchName": log.get("matches", {}).get(match_id, {}).get("name", match_id),
                        "fetchedAt": datetime.now(timezone.utc).isoformat(),
                        "source":    "admin",
                    }
                    _jsave(_KO_RESULTS_FILE, res_data)
                _ko_settle_match_bets(match_id, result)
                lb = _ko_compute_leaderboard()
                self.send_json(200, {"ok": True, "result": result, "leaderboard": lb})
                return

            self.send_json(404, {"error": "Not found"})
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.send_json(500, {"error": str(exc)})


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Pre-warm cache in background so first HTTP request is instant
    def _prewarm():
        try:
            print("Fetching bulletin (background)...")
            fetch_bulletin()
            print("Bulletin cached.")
        except Exception as exc:
            print(f"Pre-warm failed: {exc}")
    threading.Thread(target=_prewarm, daemon=True).start()

    # Background loop: check for finished KO matches and settle bets every 5 min
    def _ko_settlement_loop():
        time.sleep(30)  # let server finish initializing
        while True:
            try:
                _ko_check_and_settle_finished_matches()
            except Exception as exc:
                print(f"[ko-settlement] {exc}")
            time.sleep(300)
    threading.Thread(target=_ko_settlement_loop, daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Nesine Soccer API  →  http://localhost:{PORT}")
    print("API endpoints:")
    print(f"  GET /api/matches           football matches (default)")
    print(f"  GET /api/matches?sport=0   all sports")
    print(f"  GET /api/matches?search=X  filter by team")
    print(f"  GET /api/matches/:id       single match")
    print(f"  GET /api/markets/:mtid     markets by type ID")
    print(f"  GET /api/raw               raw bulletin JSON")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
