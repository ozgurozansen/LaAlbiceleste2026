# LaAlbiceleste2026

A zero-dependency Python server that proxies and parses the football betting api pre-match bulletin API and serves a clean, filterable soccer bet-market viewer in the browser.

## Features

- **Pure Python stdlib** — no pip install required to run
- Live bulletin fetched from `bulten.nesine.com` with a 60-second in-memory cache
- REST endpoints: `/api/matches`, `/api/matches/<id>`, `/api/markets/<mtid>`, `/api/config`, `/api/raw`
- Sports & league filtering, team search, date filter
- TR / EN language toggle
- Threaded HTTP server (handles concurrent requests)
- Single-file frontend (`public/`) — HTML + vanilla JS + CSS, no build step

## Project Structure

```
LaAlbiceleste2026/
├── server.py        # Python HTTP server + bulletin parser
├── config.json      # Sport types, market names, league mappings, outcome labels
├── public/
│   ├── index.html   # App shell
│   ├── app.js       # Frontend logic (vanilla JS)
│   └── style.css    # Styles
├── setup.sh         # One-shot dependency & environment setup script
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
python3 server.py          # listens on port 3000
python3 server.py 8080     # custom port
```

### 3. Open the UI

Navigate to [http://localhost:3000](http://localhost:3000) in your browser.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/matches` | List matches (supports `sport`, `league`, `search`, `date`, `lang` query params) |
| GET | `/api/matches/<id>` | Single match with all markets |
| GET | `/api/markets/<mtid>` | All markets of a given market type |
| GET | `/api/config` | Loaded `config.json` |
| GET | `/api/raw` | Raw bulletin JSON from Nesine |

### Query Parameters (`/api/matches`)

| Param | Default | Description |
|-------|---------|-------------|
| `sport` | `1` (Football) | Sport type ID |
| `league` | config default | Comma-separated league codes, or `0` for all |
| `search` | — | Team name substring filter |
| `date` | — | Date string filter (`YYYY-MM-DD`) |
| `lang` | `tr` | Response language: `tr` or `en` |

## Development

Python 3.8+ is required. No external packages are needed — the server uses only the standard library.

To add new market type names or outcome labels, edit `config.json`.

## License

MIT
