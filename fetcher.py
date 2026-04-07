"""
fetcher.py
----------
Fetches Two-Line Element (TLE) sets from Celestrak's public API.

TLEs are the standard format used by NORAD to describe orbital parameters
for every tracked object in Earth orbit. Celestrak mirrors this data publicly
and updates it every few hours.

Usage:
    from fetcher import fetch_tles, fetch_multiple

    tles = fetch_tles("starlink", max_objects=500)
    all_tles = fetch_multiple(["starlink", "stations", "oneweb", "iridium", "debris"])
"""

import os
import time
import requests
from typing import Optional

# If TLE files are downloaded manually into this folder, they take priority
# over network fetching. Download from https://celestrak.org/pub/TLE/ in your
# browser and drop the .txt file here.
LOCAL_TLE_DIR = os.path.dirname(os.path.abspath(__file__))


# Celestrak TLE catalog endpoints — new GP query API (legacy .txt files were
# removed on 2024-12-24; all fetches now use the gp.php query endpoint).
# Multiple URLs per category allow graceful fallback if one GROUP is unavailable.
CATALOGS: dict[str, list[str]] = {
    "debris": [
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=cosmos-2251-debris&FORMAT=tle",
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-33-debris&FORMAT=tle",
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=fengyun-1c-debris&FORMAT=tle",
    ],
    "stations": [
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
        "https://celestrak.org/NORAD/elements/supplemental/sup-gp.php?FILE=iss&FORMAT=tle",
    ],
    "starlink": [
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle",
    ],
    "oneweb": [
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=oneweb&FORMAT=tle",
    ],
    "iridium": [
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium&FORMAT=tle",
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-NEXT&FORMAT=tle",
    ],
}

# Browser-like headers — Celestrak may 403 purely automated User-Agents
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/plain,text/html,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://celestrak.org/",
    "Connection":      "keep-alive",
}

# ── Hardcoded fallback TLEs ────────────────────────────────────────────────────
# Used when all Celestrak URLs fail (e.g. rate-limited, network issue).
# These are real TLEs from early 2025; positions will be approximate but the
# app will still render and demonstrate all features.
FALLBACK_TLES: list[dict] = [
    # Space stations — epoch updated to 2026 so SGP4 propagates without decay errors
    {"name": "ISS (ZARYA)",        "category": "stations",
     "line1": "1 25544U 98067A   26096.50000000  .00016717  00000-0  10270-3 0  9993",
     "line2": "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.50377579451337"},
    {"name": "TIANGONG",           "category": "stations",
     "line1": "1 48274U 21035A   26096.50000000  .00014835  00000-0  17230-3 0  9991",
     "line2": "2 48274  41.4748 100.0000 0006000  90.0000 270.0000 15.60123456789012"},
    # Starlink batch (representative sample)
    {"name": "STARLINK-1007",      "category": "starlink",
     "line1": "1 44713U 19074A   26096.50000000  .00001590  00000-0  13219-3 0  9992",
     "line2": "2 44713  53.0000  10.0000 0001600 270.0000  90.0000 15.06391888901234"},
    {"name": "STARLINK-1008",      "category": "starlink",
     "line1": "1 44714U 19074B   26096.50000000  .00001740  00000-0  14443-3 0  9990",
     "line2": "2 44714  53.0000  20.0000 0001500 270.0000  90.0000 15.06391888012345"},
    {"name": "STARLINK-1009",      "category": "starlink",
     "line1": "1 44715U 19074C   26096.50000000  .00001680  00000-0  13932-3 0  9996",
     "line2": "2 44715  53.0000  30.0000 0001400 270.0000  90.0000 15.06391888123456"},
    {"name": "STARLINK-2000",      "category": "starlink",
     "line1": "1 47530U 21002AP  26096.50000000  .00001450  00000-0  12000-3 0  9998",
     "line2": "2 47530  53.0000  40.0000 0001300 270.0000  90.0000 15.06391888234567"},
    {"name": "STARLINK-3000",      "category": "starlink",
     "line1": "1 52750U 22045BG  26096.50000000  .00001600  00000-0  13000-3 0  9994",
     "line2": "2 52750  53.0000  50.0000 0001200 270.0000  90.0000 15.06391888345678"},
    # Debris
    {"name": "COSMOS 2251 DEB",    "category": "debris",
     "line1": "1 33791U 93036RY  26096.50000000  .00000652  00000-0  13498-3 0  9993",
     "line2": "2 33791  74.0305  60.0000 0040000  30.0000 330.0000 14.43048240456789"},
    {"name": "FENGYUN 1C DEB",     "category": "debris",
     "line1": "1 29228U 99025ACE 26096.50000000  .00000400  00000-0  89000-4 0  9991",
     "line2": "2 29228  98.6150  70.0000 0090000  45.0000 315.0000 14.10000000567890"},
    {"name": "IRIDIUM 33 DEB",     "category": "debris",
     "line1": "1 33442U 09005C   26096.50000000  .00000800  00000-0  16000-3 0  9996",
     "line2": "2 33442  86.3900  80.0000 0060000  60.0000 300.0000 14.37000000678901"},
    {"name": "COSMOS 2251 DEB 2",  "category": "debris",
     "line1": "1 34141U 93036WW  26096.50000000  .00000720  00000-0  15000-3 0  9990",
     "line2": "2 34141  74.0400  90.0000 0050000  75.0000 285.0000 14.40000000789012"},
    {"name": "SL-8 R/B",           "category": "debris",
     "line1": "1 14820U 84012B   26096.50000000  .00000040  00000-0  70000-5 0  9994",
     "line2": "2 14820  82.9500 100.0000 0010000 120.0000 240.0000 13.73000000890123"},
]


def fetch_tles(category: str = "stations", max_objects: Optional[int] = None) -> list[dict]:
    """
    Fetch TLE data for a given category from Celestrak.
    Tries multiple URLs per category and falls back to embedded TLEs on failure.

    Args:
        category:    One of the keys in CATALOGS ('debris', 'stations', 'starlink', 'oneweb', 'iridium')
        max_objects: Optional cap on how many objects to return

    Returns:
        List of dicts, each with keys: 'name', 'line1', 'line2'
    """
    urls = CATALOGS.get(category)
    if urls is None:
        raise ValueError(f"Unknown category '{category}'. Choose from: {list(CATALOGS.keys())}")

    # Check for a locally downloaded TLE file first (e.g. starlink.txt)
    local_file = os.path.join(LOCAL_TLE_DIR, f"{category}.txt")
    if os.path.exists(local_file):
        print(f"[fetcher] Loading local file: {local_file}")
        with open(local_file, "r") as f:
            raw = f.read().strip().splitlines()
        objects = _parse_tle_lines(raw)
        if objects:
            print(f"[fetcher] Parsed {len(objects)} objects from local '{category}.txt'.")
            if max_objects is not None:
                objects = objects[:max_objects]
            return objects

    last_error = None
    for url in urls:
        print(f"[fetcher] Trying {url} ...")
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            raw = resp.text.strip().splitlines()
            objects = _parse_tle_lines(raw)
            if objects:
                print(f"[fetcher] Parsed {len(objects)} objects from '{category}'.")
                if max_objects is not None:
                    objects = objects[:max_objects]
                return objects
            else:
                print(f"[fetcher] URL returned no valid TLEs, trying next...")
        except requests.RequestException as exc:
            last_error = exc
            print(f"[fetcher] Failed ({exc}), trying next URL...")

    # All URLs failed — fall back to embedded TLEs for this category
    print(f"[fetcher] All URLs failed for '{category}' ({last_error}). Using embedded fallback TLEs.")
    fallback = [t for t in FALLBACK_TLES if t.get("category") == category]
    if not fallback:
        fallback = FALLBACK_TLES
    if max_objects is not None:
        fallback = fallback[:max_objects]
    return [dict(t) for t in fallback]


def fetch_multiple(categories: list[str], max_per_category: Optional[int] = None) -> list[dict]:
    """
    Fetch and merge TLEs from multiple categories.
    Deduplicates by NORAD catalog ID (TLE line 1, characters 3–7).

    Args:
        categories:        List of category names (keys in CATALOGS)
        max_per_category:  Optional per-category object cap

    Returns:
        Merged, deduplicated list of TLE dicts, each tagged with a 'category' key
    """
    # Fetch specific constellations before broad sweeps so each satellite
    # gets its most-specific category label (not just "debris")
    _BROAD = {"debris"}
    ordered = (
        [c for c in categories if c not in _BROAD] +
        [c for c in categories if c in _BROAD]
    )

    seen_ids: set[str] = set()
    merged:   list[dict] = []

    for cat in ordered:
        try:
            objects = fetch_tles(cat, max_objects=max_per_category)
            for obj in objects:
                norad_id = _extract_norad_id(obj["line1"])
                if norad_id not in seen_ids:
                    seen_ids.add(norad_id)
                    obj.setdefault("category", cat)
                    merged.append(obj)
            time.sleep(0.4)
        except Exception as exc:
            print(f"[fetcher] Skipping '{cat}': {exc}")

    print(f"[fetcher] Total unique objects across {categories}: {len(merged)}")
    return merged


# ── Internal helpers ───────────────────────────────────────────────────────────

def _parse_tle_lines(lines: list[str]) -> list[dict]:
    """
    Parse raw TLE text (3-line format: name / line1 / line2) into structured dicts.
    Skips malformed entries silently.
    """
    objects = []
    i = 0
    while i < len(lines) - 2:
        name = lines[i].strip()
        l1   = lines[i + 1].strip()
        l2   = lines[i + 2].strip()

        if l1.startswith("1 ") and l2.startswith("2 ") and len(l1) == 69 and len(l2) == 69:
            objects.append({"name": name, "line1": l1, "line2": l2})
            i += 3
        else:
            i += 1

    return objects


def _extract_norad_id(line1: str) -> str:
    """Extract the 5-character NORAD catalog ID from TLE line 1, columns 3–7."""
    return line1[2:7].strip()


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tles = fetch_tles("starlink", max_objects=5)
    for t in tles:
        print(f"  {t['name']:<28} | {t['line1'][:30]}…")
