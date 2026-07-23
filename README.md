# LaAlbiceleste2026

A zero-dependency Python server for a friend group following the 2026 World Cup: a
live betting-odds browser, a group-stage prediction game, a knockout-stage virtual-credit
betting game, cross-tournament statistics, and an admin panel — all served from a single
Python stdlib file with a plain-JS/HTML/CSS frontend and JSON files as the database.

## Features

- **Pure Python stdlib** — no `pip install` required to run
- **Live odds browser** — bulletin proxied from `bulten.nesine.com` with a 60s in-memory
  cache, sport/league/team/date filters, TR/EN language toggle
- **Group stage prediction game** — score & result guesses per match, plus a rotating
  first-half/second-half "bonus" question (guess a player name, or a minute) per match;
  scored against admin-entered or auto-fetched (football-data.org) results, with a live
  leaderboard
- **Knockout stage betting game** — bet virtual credit against the real Nesine odds/markets
  for each knockout fixture; bets are auto-settled against ESPN box-score data, keyed by
  market type. Bet size is capped at 20% of current credit (floored at 4), with an
  admin-toggleable "unlimited betting" mode that instead caps at the player's own current
  credit (floored at 10, so it still works below zero). Users who don't bet on a match
  before kickoff take a small credit penalty. Starting credit can be exported 1:1 from a
  user's group-stage points total.
- **Statistics page** — leaderboards across both games: correct exact-score / correct-result
  / correct-bonus / correct-minute-bonus / correct-player-bonus counts for the group stage;
  bets won, biggest single win, and highest-odds win for the knockout stage
- **Champion celebration panel** — an animated full-screen reveal of the top-credit
  knockout player, shown once the final has a settled result
- **Admin panel** — enter/clear match results, trigger an ESPN results fetch + bet
  settlement, export group-stage points as knockout starting credits, review flagged
  suspiciously-fast bets, toggle unlimited betting
- Username/password auth (SHA-256 hashes, in-memory 24h tokens), per-user avatar upload
  and supported-team flag
- Threaded HTTP server; all state persisted as plain JSON files in `data/` — no external
  database

## Project Structure

```
LaAlbiceleste2026/
├── server.py                    # Python HTTP server: bulletin proxy + both games + admin API
├── config.json                  # Sport/league/market dictionaries, points config, API keys,
│                                 #   stage-redirect override
├── data/                        # JSON "database" — safe to hand-edit, tracked in git
│   ├── users.json               #   accounts (auth, display name, team, avatar, KO credit)
│   ├── groupstage2026.json      #   the 72 group-stage fixtures
│   ├── guesses.json             #   per-user score/bonus guesses (group stage)
│   ├── match_results.json       #   admin/auto-fetched group-stage results + bonus answers
│   ├── bonus_assignments.json   #   which bonus question (and input type) each match got
│   ├── bonusfirsthalf.txt       #   pool of possible 1st-half bonus questions
│   ├── bonussecondhalf.txt      #   pool of possible 2nd-half bonus questions
│   ├── squad.json               #   player/team roster data
│   ├── knockout_bets.json       #   per-user knockout bets + settlement outcome
│   ├── knockout_match_log.json  #   knockout fixtures seen so far (name, kickoff)
│   ├── knockout_results.json    #   fetched ESPN box scores for settled knockout matches
│   ├── knockout_settings.json   #   admin toggles (currently: unlimited betting)
│   └── knockout_bet_flags.json  #   suspiciously-fast bet placements (created on first hit)
├── public/
│   ├── index.html               # Auto-routes to groupstage.html or knockout.html
│   ├── groupstage.html/.js      # Group-stage prediction game UI
│   ├── knockout.html            # Odds browser + betting UI + leaderboard + champion panel
│   ├── stats.html/.js           # Cross-game statistics leaderboards
│   ├── admin.html/.js           # Admin-only result entry & controls
│   ├── app.js                   # Shared knockout-page frontend logic
│   ├── style.css                # Shared styles for all pages
│   └── img/                     # Logo + default avatar
├── setup.sh                     # One-shot environment setup script
└── README.md
```

## Quick Start

### 1. Clone & set up

```bash
git clone https://github.com/ozgurozansen/LaAlbiceleste2026.git
cd LaAlbiceleste2026
bash setup.sh
```

### 2. Run the server

```bash
python3 server.py          # listens on port 8000
python3 server.py 8080     # custom port (or set PORT=8080 in the environment)
```

### 3. Open the app

Navigate to [http://localhost:8000](http://localhost:8000). It redirects to the group-stage
game or the knockout game depending on the tournament's current stage (see
`stage_redirect` in [Configuration](#data--configuration)). Admins can reach the control
panel directly at `/admin.html`.

## API Reference

All endpoints are JSON. Endpoints under `/api/knockout/*` (except the `admin/*` ones) and
`/api/groupstage/*` that mutate state require a `token` (from login/register) passed as a
query param (GET) or body field (POST). `admin/*` endpoints additionally require the
token's user to have `isAdmin: true`.

### Odds browser

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/matches` | List matches (`sport`, `league`, `search`, `date`, `lang` query params) |
| GET | `/api/matches/<id>` | Single match with all markets |
| GET | `/api/markets/<mtid>` | All markets of a given market type |
| GET | `/api/raw` | Raw bulletin JSON from Nesine |
| GET | `/api/config` | Loaded `config.json` |
| GET | `/api/client-context` | Visitor IP-derived timezone/country (best-effort) |
| GET | `/api/stage/redirect-target` | Which stage page `/` should route to |

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create an account (username, password, display name, team, avatar) |
| POST | `/api/auth/login` | Log in, returns a 24h token |
| POST | `/api/auth/logout` | Invalidate a token |
| GET | `/api/auth/me` | Resolve a token to the current user |
| POST | `/api/auth/profile` | Update password / display name / team / avatar |
| GET | `/api/user/avatar/<username>` | Serve a user's uploaded avatar image |

### Group stage (predictions)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/groupstage/matches` | The 72 group-stage fixtures |
| GET | `/api/groupstage/squads` | Team roster data |
| POST | `/api/groupstage/guess` | Submit/update a score + bonus guess for a match |
| GET | `/api/groupstage/guesses` | Current user's own guesses |
| GET | `/api/groupstage/guesses/all` | Everyone's guesses (revealed only once a match starts) |
| GET | `/api/groupstage/results` | Entered/fetched match results |
| GET | `/api/groupstage/leaderboard` | Group-stage points leaderboard |
| POST | `/api/groupstage/result` *(admin)* | Enter a result + bonus answers |
| POST | `/api/groupstage/result/clear` *(admin)* | Remove a result |
| POST | `/api/groupstage/score` *(admin)* | Auto-fetch a result from football-data.org |

### Knockout stage (betting)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/knockout/bets` | Current user's bets, credit, and bet limits |
| POST | `/api/knockout/bet` | Place/update a bet on a match outcome |
| POST | `/api/knockout/bet/delete` | Remove a not-yet-started bet |
| GET | `/api/knockout/bets/all` | Everyone's bets per match (post-kickoff visibility) |
| GET | `/api/knockout/results` | Fetched/entered knockout match results |
| GET | `/api/knockout/leaderboard` | Knockout credit leaderboard |
| GET | `/api/knockout/champion` | Tournament champion, once the final settles |
| POST | `/api/knockout/admin/result` *(admin)* | Enter or clear a knockout result |
| POST | `/api/knockout/admin/fetch-results` *(admin)* | Fetch finished matches from ESPN + settle bets |
| POST | `/api/knockout/admin/export-gs-credits` *(admin)* | Copy group-stage points → KO starting credits |
| GET | `/api/knockout/admin/bet-flags` *(admin)* | List suspiciously-fast bet placements |
| GET/POST | `/api/knockout/admin/betting-mode` *(admin)* | View/toggle the unlimited-betting mode |

### Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats/groupstage` | Per-user prediction-accuracy counts |
| GET | `/api/stats/knockout` | Per-user bets-won / biggest-win / highest-odds-win stats |

## Data & Configuration

There is no external database — every endpoint reads/writes the JSON files in `data/`
directly (guarded by a single process-wide lock). Files are created with sane defaults
the first time they're needed, so a fresh clone with an empty `data/` directory works
fine.

`config.json` holds:
- Sport/league/market-type/outcome-label dictionaries used by the odds browser
- `defaults` — default sport & league filter
- `points` — point values for correct score/result/bonus guesses
- `results_api` / `ko_results_api` — football-data.org and ESPN settings (the former
  needs an API key; keep `config.json` out of any place you wouldn't want that key seen)
- `stage_redirect` — `force_stage: "group"|"knockout"` to override the automatic
  stage-detection that `/` uses
- `admin_password` — currently unused; admin access is controlled per-user via
  `"isAdmin": true` in `data/users.json`, not this key

**Auth tokens are in-memory** — restarting the process invalidates every logged-in
session. Since there's no hot reload, any `server.py` edit requires a restart (e.g.
`systemctl restart <service-name>` if running under systemd) to take effect, which also
means everyone gets logged out.

## Development

Python 3.8+ is required. No external packages are needed — the server uses only the
standard library. To add new market type names or outcome labels, edit `config.json`.
To promote a user to admin, set `"isAdmin": true` for them directly in `data/users.json`.

## License

MIT
