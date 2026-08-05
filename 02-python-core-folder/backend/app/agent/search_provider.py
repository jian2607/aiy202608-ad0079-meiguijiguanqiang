from __future__ import annotations

import html
import gzip
import base64
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SearchResult:
    source_id: str
    title: str
    url: str
    publisher: str
    published_at: str | None
    snippet: str
    query: str


class BingNewsRssSearchProvider:
    """Key-free news search provider used for the local MVP.

    It consumes Bing's RSS result feed only; it does not crawl result pages or
    follow article links.  The adapter is intentionally isolated so a licensed
    provider can replace it without touching the agent workflow.
    """

    endpoint = "https://www.bing.com/news/search"

    def __init__(self, timeout_seconds: float = 20):
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        url = f"{self.endpoint}?{urlencode({'q': query, 'format': 'rss', 'setlang': 'zh-Hans'})}"
        payload = self._fetch(url)
        root = ET.fromstring(payload)
        results: list[SearchResult] = []
        namespace = {"news": "https://www.bing.com/news/search"}
        for index, item in enumerate(root.findall("./channel/item")[:limit], start=1):
            title = _clean(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            snippet = _clean(item.findtext("description") or "")
            publisher = _clean(item.findtext("news:Source", namespaces=namespace) or "")
            published_at = _rss_date(item.findtext("pubDate"))
            if title and link and (snippet or title):
                results.append(SearchResult(f"{_stable_id(query, index)}", title, link, publisher, published_at, snippet, query))
        return results

    def _fetch(self, url: str) -> bytes:
        # Bing serves its RSS representation reliably to Windows' native web
        # client. Use a base64-encoded command so the search query never becomes
        # executable PowerShell syntax.
        if os.name == "nt":
            script = f"[Console]::OutputEncoding=[Text.Encoding]::UTF8; (Invoke-WebRequest -UseBasicParsing -Uri '{url}' -TimeoutSec {int(self.timeout_seconds)}).Content"
            encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                capture_output=True, text=True, encoding="utf-8", timeout=self.timeout_seconds + 5, check=False,
            )
            if completed.returncode != 0:
                raise OSError(f"bing_rss_request_failed:{completed.returncode}")
            return completed.stdout.encode("utf-8")
        request = Request(url, headers={"User-Agent": "FinancialRiskScout/0.1 (+local research use)"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                payload = gzip.decompress(payload)
            return payload


def restrict_to_window(results: Iterable[SearchResult], start: date, end: date) -> list[SearchResult]:
    """Keep only results with an explicit date inside the report-time window."""
    selected: list[SearchResult] = []
    seen: set[tuple[str, str]] = set()
    for item in results:
        if not item.published_at:
            continue
        try:
            published = date.fromisoformat(item.published_at)
        except ValueError:
            continue
        identity = (item.url, item.title)
        if start <= published <= end and identity not in seen:
            selected.append(item)
            seen.add(identity)
    return selected


def _rss_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return None


def _clean(value: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", html.unescape(value))
    return re.sub(r"\s+", " ", plain).strip()


def _stable_id(query: str, index: int) -> str:
    compact = re.sub(r"\W+", "", query)[:24] or "result"
    return f"src_{compact}_{index}"
