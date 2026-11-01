from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.core.config import get_settings


def content_security_policy(supabase_url: str | None) -> str:
    """Only our own code runs. This enforces 'no third-party scripts' (ADR 0006)."""
    supabase = f" {supabase_url.rstrip('/')}" if supabase_url else ""
    return "; ".join(
        [
            "default-src 'none'",
            "script-src 'self'",
            "style-src 'self'",
            f"img-src 'self'{supabase}",
            f"connect-src 'self'{supabase}",
            "base-uri 'none'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
    )


def security_headers() -> dict[str, str]:
    settings = get_settings()
    headers = {
        "Content-Security-Policy": content_security_policy(settings.supabase_url),
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }
    if settings.is_deployed:
        headers["Strict-Transport-Security"] = "max-age=31536000"
    return headers


def register_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.update(security_headers())
        # Pages and modules must update together: one stale module blanks the whole page.
        if not request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-cache")
        return response
