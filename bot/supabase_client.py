import httpx
from dataclasses import dataclass
from typing import Optional


@dataclass
class PodcastEntry:
    title: str
    date: str  # ISO date string e.g. "2026-02-14"
    insight: str
    post: Optional[str] = None
    link: Optional[str] = None


class SupabaseClient:
    def __init__(self, endpoint: str, api_key: str):
        self._endpoint = endpoint
        self._api_key = api_key

    def _headers(self) -> dict:
        return {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
        }

    def create_entry(self, entry: PodcastEntry) -> dict:
        """POST a new podcast entry. Returns the response JSON."""
        payload = {
            "title": entry.title,
            "date": entry.date,
            "insight": entry.insight,
        }
        if entry.post:
            payload["post"] = entry.post
        if entry.link:
            payload["link"] = entry.link

        response = httpx.post(
            self._endpoint,
            json=payload,
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def update_entry(self, entry_id: str, **fields) -> dict:
        """PUT to update an existing entry."""
        payload = {"id": entry_id, **fields}
        response = httpx.put(
            self._endpoint,
            json=payload,
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
