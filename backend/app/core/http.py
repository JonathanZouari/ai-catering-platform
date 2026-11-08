from functools import lru_cache

import httpx


@lru_cache
def client() -> httpx.Client:
    """One client for all calls to Supabase: the TLS context (loading the CA bundle is slow) and
    keep-alive connections are reused instead of being rebuilt on every request."""
    return httpx.Client(timeout=30)
