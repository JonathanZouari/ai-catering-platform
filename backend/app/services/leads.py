from datetime import date, datetime

import httpx

from app.repositories import leads
from app.services.lead_scoring import purchase_probability

OPEN_STATUSES = ("new", "contacted", "quoted")


def _scored(lead: dict) -> dict:
    inquiry_date = datetime.fromisoformat(lead["created_at"]).date()
    lead_days = (date.fromisoformat(lead["event_date"]) - inquiry_date).days
    return {**lead, "purchase_probability": purchase_probability({**lead, "lead_days": lead_days})}


def list_leads(supabase: httpx.Client, access_token: str) -> list[dict]:
    """Leads with their purchase probability.

    Open leads come first, most likely buyer on top; closed leads (won or lost) follow,
    newest first. A closed lead is scored too, so the value is ready if it is reopened.
    """
    scored = [_scored(lead) for lead in leads.list_leads(supabase, access_token)]
    # The sort is stable, so closed leads keep the repository's newest-first order.
    return sorted(
        scored,
        key=lambda lead: (
            (0, -lead["purchase_probability"]) if lead["status"] in OPEN_STATUSES else (1, 0.0)
        ),
    )
