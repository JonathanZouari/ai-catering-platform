"""Tiny Supabase REST client for back-office scripts (service role, server side only).

Stopgap until the backend has its psycopg repository layer (ARCHITECTURE.md).
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any


class SupabaseRest:
    def __init__(self, url: str | None = None, key: str | None = None) -> None:
        self.url = (url or os.environ["SUPABASE_URL"]).rstrip("/")
        if not self.url.startswith("https://"):
            raise ValueError("SUPABASE_URL must be https")
        self.key = key or os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    def _request(self, method: str, path: str, body: Any = None, prefer: str = "") -> Any:
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        request = urllib.request.Request(  # noqa: S310 - https enforced in __init__
            f"{self.url}/rest/v1/{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            raw = response.read()
            return json.loads(raw) if raw else None

    def select(self, table: str, columns: str, **filters: str) -> list[dict]:
        query = urllib.parse.urlencode({"select": columns, **filters})
        return self._request("GET", f"{table}?{query}")

    def upsert(self, table: str, rows: list[dict], on_conflict: str) -> None:
        if rows:
            query = urllib.parse.urlencode({"on_conflict": on_conflict})
            self._request("POST", f"{table}?{query}", rows, "resolution=merge-duplicates")
