"""
space_track.py
--------------
Authenticated client for the Space-Track.org REST API.

Space-Track is operated by US Space Command and is the authoritative source
for all tracked Earth-orbiting objects (~27,000+). It requires a free account
at https://www.space-track.org/auth/createAccount

Credentials are read from a .env file in the project root:

    SPACETRACK_USER=your@email.com
    SPACETRACK_PASS=yourpassword

Usage:
    from space_track import SpaceTrackClient

    with SpaceTrackClient() as st:
        tles = st.fetch("active", max_objects=500)
"""

import os
import time
import requests
from typing import Optional

# Load .env file if present (python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass   # dotenv is optional — fall back to real env vars

BASE_URL   = "https://www.space-track.org"
LOGIN_URL  = f"{BASE_URL}/ajaxauth/login"
QUERY_BASE = f"{BASE_URL}/basicspacedata/query/class/gp"

# Space-Track query predicates per category.
# Docs: https://www.space-track.org/documentation#api-basicSpaceData
#
# Key syntax rules:
#   /FIELD/VALUE          — exact match
#   /FIELD/V1,V2          — OR: exact match either value
#   /FIELD/~value~        — LIKE '%value%' (contains)
#   /FIELD/value~         — LIKE 'value%'  (starts with)
#   /FIELD/~~value        — NOT LIKE '%value%'
#   Multiple ~X~,~Y~      — OR of LIKE clauses (comma-separated)
_CATEGORY_QUERIES: dict[str, str] = {
    # Active payloads — OBJECT_TYPE = 'PAYLOAD', not decayed, epoch within 30 days
    "active": (
        f"{QUERY_BASE}"
        "/DECAY_DATE/null-val"
        "/EPOCH/%3Enow-30"
        "/OBJECT_TYPE/PAYLOAD"
        "/orderby/NORAD_CAT_ID"
        "/format/3le"
    ),
    # Debris only
    "debris": (
        f"{QUERY_BASE}"
        "/OBJECT_TYPE/DEBRIS"
        "/DECAY_DATE/null-val"
        "/orderby/NORAD_CAT_ID"
        "/format/3le"
    ),
    # Space stations — query by well-known NORAD IDs (most reliable approach)
    # 25544 = ISS, 48274 = CSS (Tiangong)
    "stations": (
        f"{QUERY_BASE}"
        "/NORAD_CAT_ID/25544,48274,53239,54216"
        "/DECAY_DATE/null-val"
        "/EPOCH/%3Enow-14"
        "/orderby/NORAD_CAT_ID"
        "/format/3le"
    ),
    # Starlink constellation — name contains STARLINK, payloads only
    "starlink": (
        f"{QUERY_BASE}"
        "/OBJECT_NAME/~~STARLINK~~"
        "/OBJECT_TYPE/PAYLOAD"
        "/DECAY_DATE/null-val"
        "/orderby/NORAD_CAT_ID"
        "/format/3le"
    ),
    # OneWeb constellation — name contains ONEWEB, payloads only
    "oneweb": (
        f"{QUERY_BASE}"
        "/OBJECT_NAME/~~ONEWEB~~"
        "/OBJECT_TYPE/PAYLOAD"
        "/DECAY_DATE/null-val"
        "/orderby/NORAD_CAT_ID"
        "/format/3le"
    ),
    # Iridium constellation — name contains IRIDIUM, payloads only
    "iridium": (
        f"{QUERY_BASE}"
        "/OBJECT_NAME/~~IRIDIUM~~"
        "/OBJECT_TYPE/PAYLOAD"
        "/DECAY_DATE/null-val"
        "/orderby/NORAD_CAT_ID"
        "/format/3le"
    ),
}


class SpaceTrackClient:
    """
    Session-based Space-Track client.
    Use as a context manager so the session is properly closed:

        with SpaceTrackClient() as st:
            tles = st.fetch("active")
    """

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self.username = username or os.getenv("SPACETRACK_USER", "")
        self.password = password or os.getenv("SPACETRACK_PASS", "")
        self._session = requests.Session()
        self._logged_in = False

        if not self.username or not self.password:
            raise ValueError(
                "Space-Track credentials not found.\n"
                "Create a .env file in the project folder with:\n"
                "  SPACETRACK_USER=your@email.com\n"
                "  SPACETRACK_PASS=yourpassword\n"
                "Register free at https://www.space-track.org/auth/createAccount"
            )

    def __enter__(self):
        self._login()
        return self

    def __exit__(self, *_):
        self.close()

    def _login(self):
        """Authenticate with Space-Track and store session cookie."""
        print("[space_track] Logging in to Space-Track.org ...")
        resp = self._session.post(
            LOGIN_URL,
            data={"identity": self.username, "password": self.password},
            timeout=15,
        )
        resp.raise_for_status()
        if "Failed" in resp.text or resp.status_code != 200:
            raise RuntimeError(
                "Space-Track login failed. Check your credentials in .env"
            )
        self._logged_in = True
        print("[space_track] Logged in successfully.")

    def fetch(self, category: str, max_objects: Optional[int] = None) -> list[dict]:
        """
        Query Space-Track for TLE data in a given category.

        Args:
            category:    One of: active, debris, stations, starlink, oneweb, iridium
            max_objects: Optional cap on returned objects

        Returns:
            List of dicts with keys: name, line1, line2, category
        """
        if not self._logged_in:
            self._login()

        query = _CATEGORY_QUERIES.get(category)
        if query is None:
            raise ValueError(f"Unknown category '{category}'. Choose from: {list(_CATEGORY_QUERIES)}")

        # Append limit if requested
        if max_objects:
            query += f"/limit/{max_objects}"

        print(f"[space_track] Fetching '{category}' ...")
        print(f"[space_track] URL: {query}")
        resp = self._session.get(query, timeout=30)
        resp.raise_for_status()

        lines = resp.text.strip().splitlines()
        objects = _parse_tle_lines(lines, category)
        print(f"[space_track] Got {len(objects)} objects for '{category}'.")

        # Space-Track rate limit: max 30 requests/min, 300/hr
        time.sleep(1.0)
        return objects

    def fetch_multiple(
        self,
        categories: list[str],
        max_per_category: Optional[int] = None,
    ) -> list[dict]:
        """
        Fetch and merge TLEs from multiple categories, deduplicated by NORAD ID.

        Named constellations (starlink, oneweb, iridium, stations) are always
        fetched BEFORE the broad 'active' and 'debris' sweeps so that each
        satellite gets its most specific category label rather than falling
        through to 'active'.
        """
        # Broad catch-all categories go last so specific ones get priority
        _BROAD = {"active", "debris"}
        ordered = (
            [c for c in categories if c not in _BROAD] +
            [c for c in categories if c in _BROAD]
        )

        seen: set[str] = set()
        merged: list[dict] = []

        for cat in ordered:
            try:
                objects = self.fetch(cat, max_objects=max_per_category)
                for obj in objects:
                    nid = obj["line1"][2:7].strip()
                    if nid not in seen:
                        seen.add(nid)
                        merged.append(obj)
            except Exception as exc:
                print(f"[space_track] Warning: could not fetch '{cat}': {exc}")

        print(f"[space_track] Total unique objects: {len(merged)}")
        return merged

    def close(self):
        self._session.close()


# ── Internal helpers ───────────────────────────────────────────────────────────

def _parse_tle_lines(lines: list[str], category: str) -> list[dict]:
    """
    Parse TLE text into structured dicts. Handles both:
      - 3-line format: name / line1 / line2  (Space-Track format/3le)
      - 2-line format: line1 / line2          (fallback)
    """
    objects = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # 3-line: name line followed by line1 + line2
        if not line.startswith("1 ") and not line.startswith("2 "):
            if i + 2 < len(lines):
                l1 = lines[i + 1].strip()
                l2 = lines[i + 2].strip()
                if (l1.startswith("1 ") and l2.startswith("2 ")
                        and len(l1) == 69 and len(l2) == 69):
                    objects.append({"name": line, "line1": l1, "line2": l2, "category": category})
                    i += 3
                    continue

        # 2-line: line1 directly, no name — derive name from NORAD ID
        if line.startswith("1 ") and len(line) == 69 and i + 1 < len(lines):
            l2 = lines[i + 1].strip()
            if l2.startswith("2 ") and len(l2) == 69:
                norad_id = line[2:7].strip()
                objects.append({"name": f"NORAD-{norad_id}", "line1": line, "line2": l2, "category": category})
                i += 2
                continue

        i += 1
    return objects


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with SpaceTrackClient() as st:
        tles = st.fetch("stations")
        for t in tles:
            print(f"  {t['name']}")
