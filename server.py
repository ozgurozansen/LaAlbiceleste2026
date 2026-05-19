#!/usr/bin/env python3
"""
Nesine Soccer Bulletin API — pure Python stdlib server
Usage: python3 server.py [port]   (default port 3000)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import threading
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
BULLETIN_URL = "https://bulten.nesine.com/api/bulten/getprebultenfull"
CACHE_TTL = 60  # seconds
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
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

# ── In-memory cache ──────────────────────────────────────────────────────────
_cache_lock = threading.Lock()
_cache = {"data": None, "fetched_at": 0}


def fetch_bulletin():
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
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

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
    # Append handicap line for corner handicap markets (e.g. "Corner Handicap (0:2.5)")
    if mtid in (798, 799) and sov != 0:
        spread = f"{abs(sov):g}"
        type_name_display = f"{type_name_display} (0:{spread})"
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
