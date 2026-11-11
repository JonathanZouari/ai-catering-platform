"""Customer orders in Supabase, through RPCs only. Server-side: this client holds the secret key."""

import logging
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import Settings

logger = logging.getLogger(__name__)
MAX_BIGINT = 2**63 - 1


class CloudUnavailable(HTTPException):
    """Any cloud failure. Deliberately says nothing about the cause; never falls back to SQLite."""

    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            detail="השירות אינו זמין כרגע. אפשר לנסות שוב; ניסיון חוזר לא ייצור הזמנה כפולה.",
            headers={"Cache-Control": "no-store"},
        )


def new_client(settings: Settings, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        base_url=f"{settings.supabase_url.rstrip('/')}/rest/v1/rpc/",
        # Secret API keys are not JWTs: they go in apikey, and the gateway applies service_role.
        headers={"apikey": settings.supabase_secret_key.get_secret_value()},
        timeout=10.0,
        # The secret must reach Supabase directly, not an ambient proxy.
        trust_env=False,
        transport=transport,
    )


def _require(value: Any, *keys: str) -> Any:
    if not isinstance(value, dict) or any(key not in value for key in keys):
        logger.error("Supabase returned an unexpected response shape")
        raise CloudUnavailable
    return value


class SupabaseOrders:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def close(self) -> None:
        self._client.close()

    def _rpc(self, name: str, **params: Any) -> Any:
        # Log only the function, status and SQLSTATE: bodies can echo customer data.
        try:
            response = self._client.post(name, json=params)
        except httpx.HTTPError as exc:
            logger.error("Supabase %s failed: %s", name, type(exc).__name__)
            raise CloudUnavailable from None
        try:
            body = response.json()
        except ValueError:
            # Not "null": a JSON null is a real answer, this is not an answer at all.
            logger.error("Supabase %s returned HTTP %s, not JSON", name, response.status_code)
            raise CloudUnavailable from None
        if response.status_code != 200:
            code = body.get("code") if isinstance(body, dict) else None
            logger.error(
                "Supabase %s returned HTTP %s (%s)",
                name,
                response.status_code,
                code if isinstance(code, str) and len(code) <= 16 else "no code",
            )
            raise CloudUnavailable
        return body

    def catalog(self) -> dict:
        return _require(self._rpc("customer_catalog"), "dishes", "zones")

    def lock_submissions(self) -> None:
        """customer_order_submit takes its own lock inside the write transaction."""

    def find(self, token_hash: str, order_id: int | None = None) -> dict | None:
        if order_id is not None and not 0 < order_id <= MAX_BIGINT:
            return None
        saved = self._rpc("customer_order_read", p_token_hash=token_hash, p_order_id=order_id)
        return None if saved is None else _require(saved, "order", "payload", "items")

    def create(self, token_hash: str, payload: str, draft: dict) -> tuple[str, dict | None]:
        result = _require(
            self._rpc(
                "customer_order_submit", p_token_hash=token_hash, p_payload=payload, p_order=draft
            ),
            "outcome",
        )
        outcome = result["outcome"]
        if outcome in ("created", "existing"):
            return outcome, _require(result.get("saved"), "order", "payload", "items")
        if outcome in ("conflict", "price_changed"):
            return outcome, None
        logger.error("Supabase customer_order_submit returned an unknown outcome")
        raise CloudUnavailable

    def decide(
        self, order_id: int, decision: str, expected_version: int, note: str
    ) -> tuple[bool, dict | None]:
        result = _require(
            self._rpc(
                "owner_order_decide",
                p_order_id=order_id,
                p_decision=decision,
                p_expected_version=expected_version,
                p_note=note,
            ),
            "decided",
            "order",
        )
        if result["order"] is None:
            return False, None
        order = _require(result["order"], "id", "status", "version", "decision_note", "decided_at")
        return result["decided"] is True, order
