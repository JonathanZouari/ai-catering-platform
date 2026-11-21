"""Lead intake and the owner's scored lead list."""

from app.repositories import leads as repo
from app.schemas.leads import LeadIn, LeadOut
from app.services.lead_scoring import is_hot, purchase_probability


def submit_lead(lead: LeadIn) -> str:
    return repo.add_lead(lead.model_dump(mode="json"))


def scored_leads() -> list[LeadOut]:
    out = []
    for row in [*repo.form_leads(), *repo.demo_leads()]:
        used_chat = str(row["used_chat"]).lower() in ("1", "true")
        features = {**row, "used_chat": int(used_chat)}
        p = purchase_probability(features)
        out.append(
            LeadOut(
                lead_id=row["lead_id"],
                full_name=row["full_name"],
                phone=row["phone"],
                event_type=row["event_type"],
                guests=int(row["guests"]),
                days_until_event=int(row["days_until_event"]),
                budget_per_guest=int(row["budget_per_guest"]),
                dishes_viewed=int(row["dishes_viewed"]),
                visits=int(row["visits"]),
                source=row["source"],
                used_chat=used_chat,
                probability=round(p, 4),
                is_hot=is_hot(p),
                is_demo=row["is_demo"],
            )
        )
    return sorted(out, key=lambda lead: lead.probability, reverse=True)
