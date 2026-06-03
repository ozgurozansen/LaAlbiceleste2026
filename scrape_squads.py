#!/usr/bin/env python3
"""
scrape_squads.py
Fetches 2026 FIFA World Cup squad data from Wikipedia → data/squad.json.

Run:  python scrape_squads.py
Re-run at any time to update the file with the latest squads.
"""

# ── auto-install missing dependencies ────────────────────────────────────────
import sys
import subprocess
import importlib

for _pkg, _imp in [
    ("requests",       "requests"),
    ("beautifulsoup4", "bs4"),
    ("lxml",           "lxml"),
]:
    try:
        importlib.import_module(_imp)
    except ImportError:
        print(f"[setup] Installing {_pkg} …")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", _pkg, "-q"],
            stdout=subprocess.DEVNULL,
        )

# ─────────────────────────────────────────────────────────────────────────────
import json
import os
import re

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# ── constants ─────────────────────────────────────────────────────────────────
WIKI_URL  = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads"
OUTPUT    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "squad.json")
# Matches a position code optionally preceded by a jersey number, e.g. "1 GK"
POS_RE    = re.compile(r"\b(GK|DF|MF|FW)\b")
GROUP_RE  = re.compile(r"^Group [A-L]$")
HEADERS   = {"User-Agent": "LaAlbiceleste2026-SquadScraper/1.0"}


# ── helpers ───────────────────────────────────────────────────────────────────

def _fetch(url):
    """Download a URL and return a BeautifulSoup tree."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def _cell_text(td):
    """Return whitespace-normalised plain text of a table cell."""
    return re.sub(r"\s+", " ", td.get_text(" ")).strip()


def _club_from_cell(td):
    """
    Return the actual club name from a club cell.
    Wikipedia club cells contain a flag icon (whose alt text is the federation
    name) followed by an <a> link to the club.  Taking the last link gives the
    club name cleanly.
    """
    links = [a.get_text(strip=True) for a in td.find_all("a")]
    # filter out single digits / empty strings
    links = [l for l in links if l and not l.isdigit() and len(l) > 1]
    return links[-1] if links else _cell_text(td)


def _parse_row(row):
    """
    Parse a single <tr> into a player dict.
    Returns None for header / separator rows.

    Current Wikipedia format (2026) combines jersey number and position in one
    cell, e.g. "1 GK".  Older format had separate columns.  Both are handled
    by searching for the cell whose text contains a position code.
    """
    tds   = row.find_all(["td", "th"])
    texts = [_cell_text(td) for td in tds]

    # Find the column whose text contains a position code (GK/DF/MF/FW)
    pos_idx = next((i for i, t in enumerate(texts) if POS_RE.search(t)), None)
    if pos_idx is None:
        return None
    # need at least 5 more columns: name, dob, caps, goals, club
    if len(tds) < pos_idx + 6:
        return None

    # Extract position and optional jersey number from the cell.
    # New format: "1 GK"  →  jersey=1, pos="GK"
    # Old format: "GK"    →  jersey from previous column (if digit)
    pos_cell = texts[pos_idx]
    m        = POS_RE.search(pos_cell)
    pos      = m.group(1)
    pre      = pos_cell[: m.start()].strip()
    jersey   = int(pre) if pre.isdigit() else None
    if jersey is None and pos_idx >= 1 and texts[pos_idx - 1].strip().isdigit():
        jersey = int(texts[pos_idx - 1].strip())

    name_raw = texts[pos_idx + 1]
    captain  = bool(re.search(r"\(captain\)", name_raw, re.I))
    name     = re.sub(r"\s*\(captain\)\s*", "", name_raw, flags=re.I).strip()

    dob_raw = texts[pos_idx + 2]
    dob_m   = re.search(r"([A-Z][a-z]+ \d+,?\s*\d{4})", dob_raw)
    dob     = dob_m.group(1).replace(",", "").strip() if dob_m else dob_raw.split("(")[0].strip()
    age_m   = re.search(r"aged\s+(\d+)", dob_raw, re.I)
    age     = int(age_m.group(1)) if age_m else None

    try:
        caps  = int(re.sub(r"\D", "", texts[pos_idx + 3]) or "0")
    except ValueError:
        caps  = 0
    try:
        goals = int(re.sub(r"\D", "", texts[pos_idx + 4]) or "0")
    except ValueError:
        goals = 0

    club = _club_from_cell(tds[pos_idx + 5])

    player = {
        "name":          name,
        "position":      pos,
        "date_of_birth": dob,
        "age":           age,
        "caps":          caps,
        "goals":         goals,
        "club":          club,
        "captain":       captain,
    }
    if jersey is not None:
        player["jersey_number"] = jersey
    return player


# ── main parser ───────────────────────────────────────────────────────────────

def parse_squads(soup):
    """
    Walk the article content, tracking group/team headings, coach paragraphs,
    and squad wikitables.

    Modern Wikipedia wraps headings in <div class="mw-heading mw-heading2/3">.
    The actual content lives in div.mw-content-ltr.
    """
    # Try the modern container first, fall back to mw-parser-output or body
    root = (
        soup.find(class_="mw-content-ltr")
        or soup.find(class_="mw-parser-output")
        or soup.body
    )

    groups    = []
    cur_group = None
    cur_team  = None

    for elem in root.children:
        tag     = getattr(elem, "name", None)
        classes = elem.get("class", []) if tag else []
        if not tag:
            continue

        # ── Group heading ─────────────────────────────────────────────────────
        # Modern:  <div class="mw-heading mw-heading2"><h2>Group A</h2>…</div>
        # Legacy:  <h2><span class="mw-headline">Group A</span>…</h2>
        if tag == "div" and "mw-heading2" in classes:
            h = elem.find("h2")
            text = (h or elem).get_text(strip=True)
            if GROUP_RE.match(text):
                cur_group = {"group": text, "teams": []}
                groups.append(cur_group)
                cur_team = None
            else:
                # Non-group section (e.g. "Statistics") — stop collecting
                cur_group = None
                cur_team  = None

        elif tag == "h2":
            span = elem.find(class_="mw-headline") or elem
            text = span.get_text(strip=True)
            if GROUP_RE.match(text):
                cur_group = {"group": text, "teams": []}
                groups.append(cur_group)
                cur_team = None
            else:
                cur_group = None
                cur_team  = None

        # ── Team heading ──────────────────────────────────────────────────────
        elif tag == "div" and "mw-heading3" in classes and cur_group:
            h = elem.find("h3")
            team_name = (h or elem).get_text(strip=True)
            cur_team  = {"team": team_name, "coach": None, "players": []}
            cur_group["teams"].append(cur_team)

        elif tag == "h3" and cur_group:
            span = elem.find(class_="mw-headline") or elem
            team_name = span.get_text(strip=True)
            cur_team  = {"team": team_name, "coach": None, "players": []}
            cur_group["teams"].append(cur_team)

        # ── Coach paragraph ───────────────────────────────────────────────────
        elif tag == "p" and cur_team and cur_team["coach"] is None:
            if re.search(r"\bCoach\b", elem.get_text(), re.I):
                links = [
                    a.get_text(strip=True)
                    for a in elem.find_all("a")
                    if a.get_text(strip=True)
                ]
                if links:
                    cur_team["coach"] = links[-1]

        # ── Squad table ───────────────────────────────────────────────────────
        elif tag == "table" and cur_team:
            if "wikitable" in classes:
                for row in elem.find_all("tr"):
                    player = _parse_row(row)
                    if player:
                        cur_team["players"].append(player)

    return groups


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    print(f"Fetching  {WIKI_URL} …")
    soup   = _fetch(WIKI_URL)

    print("Parsing …")
    groups = parse_squads(soup)

    n_teams   = sum(len(g["teams"])   for g in groups)
    n_players = sum(len(t["players"]) for g in groups for t in g["teams"])
    print(f"  {len(groups)} groups  |  {n_teams} teams  |  {n_players} players")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source":       WIKI_URL,
        "groups":       groups,
    }

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)

    print(f"Saved  →  {OUTPUT}")


if __name__ == "__main__":
    main()
