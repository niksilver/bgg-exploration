import json
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import requests

BGG_API_BASE       = "https://boardgamegeek.com/xmlapi2"
RATE_LIMIT_SECS    = 2.0
DEFAULT_TOKEN_PATH = Path(__file__).parent.parent / "data" / "token.json"


@dataclass(frozen=True)
class GameSearchResult:
    bgg_id: int
    name:   str
    year:   int | None


@dataclass(frozen=True)
class GameDetails:
    bgg_id:     int
    name:       str
    year:       int | None
    rating_avg: float | None
    bgg_rank:   int | None


class BGGClient:
    def __init__(
        self,
        session:    requests.Session | None = None,
        token_path: Path | None = None,
    ):
        self._session      = session or requests.Session()
        self._last_request = 0.0

        path = token_path if token_path is not None else DEFAULT_TOKEN_PATH
        if path.exists():
            token = json.loads(path.read_text())["value"]
            self._session.headers["Authorization"] = f"Bearer {token}"

    def _get(self, endpoint: str, params: dict) -> ET.Element:
        elapsed = time.monotonic() - self._last_request
        if elapsed < RATE_LIMIT_SECS:
            time.sleep(RATE_LIMIT_SECS - elapsed)

        url = f"{BGG_API_BASE}/{endpoint}"
        for attempt in range(3):
            resp = self._session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                self._last_request = time.monotonic()
                return ET.fromstring(resp.text)
            if resp.status_code == 429:
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
            else:
                resp.raise_for_status()

        raise RuntimeError(f"BGG API failed after 3 attempts: {url}")

    def search(self, query: str) -> list[GameSearchResult]:
        root = self._get("search", {"query": query, "type": "boardgame"})
        results = []
        for item in root.findall("item"):
            bgg_id   = int(item.get("id"))
            name_el  = item.find("name[@type='primary']")
            name     = name_el.get("value") if name_el is not None else "Unknown"
            year_el  = item.find("yearpublished")
            year     = int(year_el.get("value")) if year_el is not None else None
            results.append(GameSearchResult(bgg_id=bgg_id, name=name, year=year))
        return results

    def fetch(self, bgg_id: int) -> GameDetails | None:
        root = self._get("thing", {"id": bgg_id, "type": "boardgame", "stats": 1})
        item = root.find("item")
        if item is None:
            return None

        name_el = item.find("name[@type='primary']")
        name    = name_el.get("value") if name_el is not None else "Unknown"
        year_el = item.find("yearpublished")
        year    = int(year_el.get("value")) if year_el is not None else None

        rating_avg = None
        avg_el = item.find(".//average")
        if avg_el is not None:
            try:
                rating_avg = float(avg_el.get("value"))
            except (ValueError, TypeError):
                pass

        bgg_rank = None
        rank_el = item.find(".//rank[@name='boardgame']")
        if rank_el is not None:
            try:
                bgg_rank = int(rank_el.get("value"))
            except (ValueError, TypeError):
                pass

        return GameDetails(
            bgg_id=bgg_id, name=name, year=year,
            rating_avg=rating_avg, bgg_rank=bgg_rank,
        )
