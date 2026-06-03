#!/usr/bin/env python3
"""
LaAlbiceleste2026 API — pure Python stdlib server
Usage: python3 server.py [port]   (default port 3000)
"""

import http.client
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
import uuid
from datetime import datetime, timezone, timedelta

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
BULLETIN_URL = "https://bulten.nesine.com/api/bulten/getprebultenfull"
CACHE_TTL = 60  # seconds
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
DATA_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


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
OUTCOME_LABELS    = {int(k): {int(n): v for n, v in oc.items()}
                     for k, oc in CONFIG.get("outcome_labels", {}).items()}
OUTCOME_LABELS_TR = {int(k): {int(n): v for n, v in oc.items()}
                     for k, oc in CONFIG.get("outcome_labels_tr", {}).items()}
SPORT_TYPES_TR    = {int(k): v for k, v in CONFIG.get("sport_types_tr", {}).items()}
_TR_TO_EN         = CONFIG.get("tr_to_en", {})

# ── Group-stage data paths ────────────────────────────────────────────────────
_GS_FILE    = os.path.join(DATA_DIR, "groupstage2026.json")
_BFH_FILE   = os.path.join(DATA_DIR, "bonusfirsthalf.txt")
_BSH_FILE   = os.path.join(DATA_DIR, "bonussecondhalf.txt")
_SQUAD_FILE = os.path.join(DATA_DIR, "squad.json")
_USERS_FILE = os.path.join(DATA_DIR, "users.json")
_GUESS_FILE = os.path.join(DATA_DIR, "guesses.json")
_RES_FILE   = os.path.join(DATA_DIR, "match_results.json")

POINTS_CFG  = CONFIG.get("points", {"correct_score": 5, "correct_result": 3,
                                     "correct_fh_bonus": 1, "correct_sh_bonus": 1})


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
_data_lock     = threading.Lock()
_tokens        = {}   # token -> {username, expires}


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


def _enrich_match(idx, m):
    n_fh = len(_BONUS_FH)
    n_sh = len(_BONUS_SH)
    fhb  = _BONUS_FH[idx % n_fh] if n_fh else None
    shb  = _BONUS_SH[idx % n_sh] if n_sh else None
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
                   "totalPoints": total, "matchPoints": match_pts})
    lb.sort(key=lambda x: -x["totalPoints"])
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


def format_market(market, lang="tr"):
    mtid = market.get("MTID", 0)
    sov  = market.get("SOV") or 0
    type_name = MARKET_TYPE_NAMES.get(mtid, f"Market #{mtid}")
    outcomes = [
        {
            "n":     oc.get("N", 0),
            "label": _outcome_label(mtid, oc.get("N", 0), sov, oc.get("ON"), lang),
            "odds":  oc.get("O"),
            "no":    oc.get("NO"),
        }
        for oc in market.get("OCA", [])
    ]
    mn = market.get("MN")
    if lang == "tr":
        type_name_display = MARKET_TYPE_NAMES_TR.get(mtid) or mn or f"Pazar #{mtid}"
    else:
        type_name_display = MARKET_TYPE_NAMES.get(mtid) or (_TR_TO_EN.get(mn, mn) if mn else None) or f"Market #{mtid}"
    # Append handicap line for European Handicap markets (e.g. "Handicap Match Result (0:1)")
    if mtid in _EH_MTIDS and sov != 0:
        if sov < 0:
            type_name_display = f"{type_name_display} (0:{abs(sov):g})"
        else:
            type_name_display = f"{type_name_display} ({sov:g}:0)"
    # Append handicap line for corner handicap markets (e.g. "Corner Handicap (0:2.5)" or "Corner Handicap (0.5:0)")
    elif mtid in (798, 799) and sov != 0:
        spread = f"{abs(sov):g}"
        if sov < 0:
            type_name_display = f"{type_name_display} (0:{spread})"
        else:
            type_name_display = f"{type_name_display} ({spread}:0)"
    # Append spread for Result + Over/Under (e.g. "Result + Over/Under (+3.5)")
    elif mtid == 272 and sov != 0:
        sign = "+" if sov > 0 else ""
        type_name_display = f"{type_name_display} ({sign}{sov:g})"
    return {
        "id":          market.get("ID"),
        "no":          market.get("NO"),
        "typeId":      mtid,
        "typeName":    type_name_display,
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
        "homeTeam": ev.get("HN", ""),
        "awayTeam": ev.get("AN", ""),
        "displayName": ev.get("ENO") or f"{ev.get('HN','')} - {ev.get('AN','')}",
        "sportType": ev.get("TYPE"),
        "sportName": sport_types_map.get(ev.get("TYPE", 0), f"Type {ev.get('TYPE')}"),
        "date": ev.get("D", ""),
        "day": ev.get("DAY", ""),
        "time": ev.get("T", ""),
        "startTimestamp": ev.get("ESD"),
        "leagueCode": ev.get("LC"),
        "leagueName": league_names.get(ev.get("LC"), f"League #{ev.get('LC')}"),
        "isLive": ev.get("LE") == 1,
        "markets": [format_market(m, lang) for m in ev.get("MA", [])],
        "marketCount": len(ev.get("MA", [])),
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

                self.send_json(200, {
                    "total": len(filtered),
                    "cacheAge": int(time.time() - fetched_at),
                    "sportTypes": sport_types_list,
                    "leagues": leagues_list,
                    "activeLeagues": league_filter,
                    "matches": [format_event(e, lang, league_names) for e in filtered],
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

            # ── /api/raw ───────────────────────────────────────────────────
            if path == "/api/raw":
                raw, _ = fetch_bulletin()
                self.send_json(200, raw)
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
                })
                return

            # ── /api/groupstage/matches ────────────────────────────────────
            if path == "/api/groupstage/matches":
                enriched = [_enrich_match(i, m) for i, m in enumerate(_ALL_MATCHES)
                            if "group" in m]
                self.send_json(200, {"matches": enriched})
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

            # ── /api/groupstage/results ────────────────────────────────────
            if path == "/api/groupstage/results":
                token    = qs.get("token", [""])[0]
                username = _validate_token(token)
                rdata    = _jload(_RES_FILE, {"results": {}})
                if username and _is_admin(username):
                    self.send_json(200, rdata)
                else:
                    pub = {k: {"score": v.get("score"), "scored": v.get("scored", False)}
                           for k, v in rdata.get("results", {}).items()}
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
                if not uname or not pw:
                    self.send_json(400, {"error": "Username and password required"})
                    return
                if not (3 <= len(uname) <= 30):
                    self.send_json(400, {"error": "Username: 3–30 characters"})
                    return
                if not re.match(r'^[a-z0-9_]+$', uname):
                    self.send_json(400, {"error": "Username: lowercase letters, digits, underscores only"})
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
                        "createdAt":   datetime.now(timezone.utc).isoformat(),
                    }
                    _jsave(_USERS_FILE, users)
                token = _create_token(uname)
                self.send_json(201, {"token": token, "username": uname,
                                     "displayName": display, "isAdmin": False})
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
                })
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
                self.send_json(200, {"ok": True, "leaderboard": _compute_leaderboard()})
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
                self.send_json(200, {"ok": True, "result": result,
                                     "leaderboard": _compute_leaderboard()})
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
