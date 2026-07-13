"""ruTracker search and torrent link resolution."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from autoairac.config import RuTrackerConfig

logger = logging.getLogger(__name__)

_TOPIC_ID_RE = re.compile(r"viewtopic\.php\?t=(\d+)")
_CYCLE_RE = re.compile(r"\bAIRAC\s+(\d{4})\b", re.IGNORECASE)
_FALLBACK_CYCLE_RE = re.compile(r"\b(\d{4})\b")
_NAV_KEYWORDS = ("airac", "navigraph", "navdata", "навигацион", "navigation")


@dataclass(frozen=True)
class TorrentSearchResult:
    topic_id: int
    title: str
    cycle: int | None
    download_url: str


class RuTrackerClient:
    """Minimal ruTracker client for AIRAC torrent discovery."""

    def __init__(self, config: RuTrackerConfig) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutoAIRAC/0.1",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            },
        )
        self._logged_in = False

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RuTrackerClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def login(self) -> None:
        if self._logged_in:
            return
        if not self._config.username or not self._config.password:
            logger.warning("ruTracker credentials not configured — download may fail.")
            return

        response = self._client.post(
            "/forum/login.php",
            data={
                "login_username": self._config.username,
                "login_password": self._config.password,
                "login": "Вход",
            },
        )
        response.raise_for_status()

        if "login.php?logout" not in response.text and "logged-in-username" not in response.text:
            index = self._client.get("/forum/index.php")
            if "logged-in-username" not in index.text:
                logger.error("ruTracker login failed — check username/password.")
                return

        self._logged_in = True
        logger.debug("ruTracker login successful.")

    def find_airac_torrent(self, target_cycle: int) -> TorrentSearchResult | None:
        self.login()

        if self._config.topic_id:
            return self._resolve_topic(self._config.topic_id, target_cycle)

        queries = [
            self._config.search_query.format(cycle=target_cycle),
            f"AIRAC {target_cycle}",
            f"Navigraph AIRAC {target_cycle}",
        ]
        seen_queries: set[str] = set()
        for query in queries:
            if query in seen_queries:
                continue
            seen_queries.add(query)
            results = self._search(query)
            match = self._pick_best(results, target_cycle)
            if match is not None:
                topic_id, title = match
                resolved = self._resolve_topic(topic_id, target_cycle, title=title)
                if resolved is not None:
                    return resolved

        logger.info(
            "Direct search missed AIRAC %s — scanning recent Navigraph releases.",
            target_cycle,
        )
        broad = self._search("Navigraph")
        match = self._pick_best(broad, target_cycle, require_exact_cycle=True)
        if match is None:
            return None
        topic_id, title = match
        return self._resolve_topic(topic_id, target_cycle, title=title)

    def _search(self, query: str) -> list[tuple[int, str]]:
        response = self._client.get(
            "/forum/tracker.php",
            params={"nm": query},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        hits: list[tuple[int, str]] = []
        for link in soup.select("a.tLink, a.tracker__topic-title"):
            href = link.get("href", "")
            match = _TOPIC_ID_RE.search(href)
            if not match:
                continue
            topic_id = int(match.group(1))
            title = link.get_text(" ", strip=True)
            lowered = title.lower()
            if any(keyword in lowered for keyword in _NAV_KEYWORDS):
                hits.append((topic_id, title))

        result_count = self._result_count(soup)
        logger.debug(
            "ruTracker search %r -> %s hit(s), %s parsed",
            query,
            result_count,
            len(hits),
        )
        return hits

    @staticmethod
    def _result_count(soup: BeautifulSoup) -> str:
        for text in soup.stripped_strings:
            if "Результатов поиска" in text:
                return text
        return "unknown"

    def _pick_best(
        self,
        results: list[tuple[int, str]],
        target_cycle: int,
        *,
        require_exact_cycle: bool = False,
    ) -> tuple[int, str] | None:
        exact: list[tuple[int, str]] = []
        fallback: list[tuple[int, str]] = []
        for topic_id, title in results:
            cycle = self._extract_cycle(title)
            if cycle == target_cycle:
                exact.append((topic_id, title))
            elif cycle is not None and not require_exact_cycle:
                fallback.append((topic_id, title))

        if exact:
            return exact[0]
        if require_exact_cycle:
            return None
        return fallback[0] if fallback else None

    def _resolve_topic(
        self,
        topic_id: int,
        target_cycle: int,
        *,
        title: str | None = None,
    ) -> TorrentSearchResult | None:
        response = self._client.get(f"/forum/viewtopic.php?t={topic_id}")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        if title is None:
            title_tag = soup.select_one("h1.tm-title, h1")
            title = title_tag.get_text(strip=True) if title_tag else f"Topic {topic_id}"

        magnet = soup.select_one("a.magnet-link")
        if magnet and magnet.get("href"):
            return TorrentSearchResult(
                topic_id=topic_id,
                title=title,
                cycle=self._extract_cycle(title) or target_cycle,
                download_url=magnet["href"],
            )

        torrent_link = soup.select_one("a.link-dl-attach, a[href*='dl.php?t=']")
        if torrent_link and torrent_link.get("href"):
            href = torrent_link["href"]
            if not href.startswith("http"):
                href = urljoin(self._config.base_url, href)
            return TorrentSearchResult(
                topic_id=topic_id,
                title=title,
                cycle=self._extract_cycle(title) or target_cycle,
                download_url=href,
            )

        dl_button = soup.find("a", string=re.compile(r"\.torrent", re.I))
        if dl_button and dl_button.get("href"):
            href = dl_button["href"]
            if not href.startswith("http"):
                href = urljoin(self._config.base_url, href)
            return TorrentSearchResult(
                topic_id=topic_id,
                title=title,
                cycle=self._extract_cycle(title) or target_cycle,
                download_url=href,
            )

        logger.warning("No download link found for topic %s", topic_id)
        return None

    @staticmethod
    def _extract_cycle(title: str) -> int | None:
        match = _CYCLE_RE.search(title)
        if match:
            return int(match.group(1))
        matches = _FALLBACK_CYCLE_RE.findall(title)
        if not matches:
            return None
        return int(matches[-1])