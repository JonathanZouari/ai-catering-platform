"""Generate a synthetic leads dataset for a purchase-probability (logistic regression) model.

Each row is one lead: the event form fields plus session/context signals captured when the
lead was submitted. The label `purchased` is drawn from a hidden logistic model
(`TRUE_EFFECTS`), so a trained model can be checked against known ground truth.

Values (event types, cities, slots) mirror frontend/js/customer/mock-backend.js, which are
PLACEHOLDERS, not business rules. The data is fake; never mix it with real leads.

Usage (from backend/):  uv run python -m ml.generate_leads --rows 5000 --seed 42
"""

import argparse
import csv
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path

EVENT_TYPES = [
    "יום הולדת",
    "אירוע משפחתי",
    "בר או בת מצווה",
    "ארוחת שבת",
    "יום נישואין",
    "חגיגה פרטית",
    "אחר",
]
CITIES = ["תל אביב-יפו", "רמת גן", "גבעתיים", "הרצליה", "פתח תקווה", "ראשון לציון"]
SLOTS = {
    "pickup": ["10:00-12:00", "12:00-14:00", "15:00-17:00"],
    "delivery": ["09:00-11:00", "11:00-13:00", "14:00-16:00"],
}

# Hidden ground truth: additive contributions to the purchase log-odds.
# `browser` and `os` deliberately have no effect, so a good model should find ~0 for them.
TRUE_EFFECTS = {
    "intercept": -4.4,
    "event_type": {"בר או בת מצווה": 0.5, "ארוחת שבת": 0.25, "אירוע משפחתי": 0.15, "אחר": -0.4},
    "lead_days_short": -0.9,  # event in fewer than 4 days
    "lead_days_far": -0.6,  # event more than 90 days away
    "log_guests": 0.25,
    "has_phone": 0.7,
    "has_notes": 0.3,
    "log_time_on_site": 0.35,
    "pages_viewed": 0.06,
    "returning_visitor": 0.5,
    "used_ai_chat": 0.4,
    "has_draft": 0.9,
    "traffic_source": {
        "referral": 0.6,
        "google_ads": 0.2,
        "direct": 0.1,
        "instagram": -0.2,
        "facebook": -0.1,
    },
    "device_mobile": -0.2,
    "night_visit": -0.4,  # 00:00-05:59
    "browser_language": {"en": -0.3, "ru": -0.1, "ar": -0.2, "other": -0.5},
    "bot_like_form": -2.5,  # form filled in under 15 seconds
    "business_customer": 0.3,
    "past_customer": 1.0,
    "requested_callback": 0.6,
    "budget_stated": 0.3,
    "budget_low": -0.9,  # stated budget under 70 ILS per guest
    "kashrut": {"mehadrin": -0.3},
    "contact_whatsapp": 0.2,
    "marketing_consent": 0.2,
    # age_group has no true effect on purpose: it should not drive the score.
}

# Invented contact details. Emails use example.com (RFC 2606) so they can never reach anyone.
FIRST_NAMES_HE = [
    "נועה",
    "יעל",
    "מיכל",
    "שירה",
    "תמר",
    "אביגיל",
    "רונית",
    "דנה",
    "מאיה",
    "הילה",
    "יוסי",
    "דוד",
    "אבי",
    "משה",
    "עומר",
    "איתי",
    "רון",
    "אלון",
    "יונתן",
    "גיל",
]
LAST_NAMES_HE = [
    "כהן",
    "לוי",
    "מזרחי",
    "פרץ",
    "ביטון",
    "אברהם",
    "פרידמן",
    "שפירא",
    "אזולאי",
    "דהן",
    "גולן",
    "שרון",
    "קפלן",
    "רוזן",
    "ברק",
    "נחום",
    "חדד",
    "אוחיון",
]
FIRST_NAMES_EN = ["Daniel", "Sarah", "Michael", "Rachel", "David", "Emily", "Jonathan", "Hannah"]
LAST_NAMES_EN = ["Cohen", "Levy", "Miller", "Klein", "Gold", "Stern", "Weiss", "Katz"]
COMPANY_NAMES = [
    "סטארט־אפ אלפא",
    "משרד עו״ד בן דוד",
    "הייטק נקסט",
    "קבוצת אורן",
    "סטודיו גל",
    "חברת לוטם",
    "בית תוכנה אופק",
    "רשת ירוק",
]
EMAIL_SLUGS = ["user", "family", "events", "home", "mail"]

FIELDS = [
    # identity / timing
    "lead_id",
    "created_at",
    # customer (invented)
    "full_name",
    "phone",
    "email",
    "preferred_contact",
    "customer_type",
    "company_name",
    "age_group",
    "residence_city",
    "is_past_customer",
    "past_orders",
    "past_spend_ils",
    "marketing_consent",
    "requested_callback",
    "budget_per_guest_ils",
    "kashrut",
    "venue_type",
    # event form
    "event_type",
    "event_date",
    "days_until_event",
    "slot",
    "fulfillment",
    "city",
    "adults",
    "children",
    "vegetarian",
    "vegan",
    "restricted",
    "notes_length",
    "has_phone",
    "has_email",
    # session and context
    "device",
    "browser",
    "os",
    "browser_language",
    "visit_hour",
    "visit_weekday",
    "traffic_source",
    "time_on_site_sec",
    "pages_viewed",
    "viewed_menu",
    "form_fill_sec",
    "returning_visitor",
    "previous_visits",
    "used_ai_chat",
    "ai_messages",
    "dishes_in_draft",
    "draft_total_ils",
    # label
    "purchased",
]


def _pick(rng: random.Random, weights: dict):
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def _lognormal_int(rng: random.Random, median: float, sigma: float, lo: int, hi: int) -> int:
    return max(lo, min(hi, round(rng.lognormvariate(math.log(median), sigma))))


def make_lead(rng: random.Random, i: int, start: datetime) -> dict:
    created = start + timedelta(minutes=rng.randrange(365 * 24 * 60))
    hour = _pick(rng, {h: (0.3 if h < 6 else 2.0 if 19 <= h <= 23 else 1.2) for h in range(24)})
    created = created.replace(hour=hour)

    event_type = _pick(rng, dict(zip(EVENT_TYPES, [18, 22, 15, 14, 8, 15, 8], strict=True)))
    days_until = max(2, min(240, round(rng.lognormvariate(math.log(25), 0.9))))
    event_date = created.date() + timedelta(days=days_until)
    fulfillment = _pick(rng, {"delivery": 65, "pickup": 35})
    city = rng.choice(CITIES) if fulfillment == "delivery" else ""

    base_guests = {"בר או בת מצווה": 70, "אירוע משפחתי": 40, "ארוחת שבת": 18}.get(event_type, 25)
    adults = _lognormal_int(rng, base_guests, 0.5, 1, 300)
    children = _lognormal_int(rng, adults * 0.35, 0.7, 0, 150) if rng.random() < 0.6 else 0
    total = adults + children
    vegetarian = rng.binomialvariate(total, 0.08) if rng.random() < 0.5 else 0
    vegan = rng.binomialvariate(total, 0.03) if rng.random() < 0.3 else 0
    restricted = rng.binomialvariate(total, 0.05) if rng.random() < 0.35 else 0
    notes_length = _lognormal_int(rng, 60, 0.8, 5, 500) if rng.random() < 0.3 else 0

    device = _pick(rng, {"mobile": 68, "desktop": 28, "tablet": 4})
    if device == "desktop":
        browser = _pick(rng, {"chrome": 65, "edge": 18, "safari": 10, "firefox": 7})
        os_name = "macos" if browser == "safari" else _pick(rng, {"windows": 80, "macos": 20})
    else:
        os_name = _pick(rng, {"ios": 45, "android": 55})
        browser = (
            _pick(rng, {"safari": 85, "chrome": 15})
            if os_name == "ios"
            else _pick(rng, {"chrome": 75, "samsung": 20, "other": 5})
        )
    lang = _pick(rng, {"he": 82, "en": 8, "ru": 6, "ar": 2, "other": 2})
    if rng.random() < 0.03:
        lang = ""  # not reported by the browser

    source = _pick(
        rng,
        {
            "google_ads": 25,
            "organic": 25,
            "instagram": 18,
            "facebook": 10,
            "referral": 10,
            "direct": 12,
        },
    )
    returning = rng.random() < 0.25
    previous_visits = _lognormal_int(rng, 2, 0.6, 1, 15) if returning else 0
    pages = _lognormal_int(rng, 5, 0.6, 1, 40)
    time_on_site = _lognormal_int(rng, 240, 0.8, 10, 3600)
    form_fill = _lognormal_int(rng, 90, 0.5, 20, 900)
    if rng.random() < 0.015:  # bot-like submission
        pages, time_on_site, form_fill = 1, rng.randint(2, 15), rng.randint(2, 14)
    viewed_menu = pages > 2 and rng.random() < 0.75
    used_ai = rng.random() < 0.2
    ai_messages = _lognormal_int(rng, 4, 0.6, 1, 40) if used_ai else 0
    dishes = rng.randint(1, 12) if viewed_menu and rng.random() < 0.55 else 0
    per_guest = rng.uniform(70, 160)
    draft_total = round(total * per_guest * min(1.0, dishes / 6) + 120) if dishes else 0
    has_phone = rng.random() < 0.7
    has_email = (not has_phone) or rng.random() < 0.6

    # customer profile
    if lang == "en":
        first, last = rng.choice(FIRST_NAMES_EN), rng.choice(LAST_NAMES_EN)
    else:
        first, last = rng.choice(FIRST_NAMES_HE), rng.choice(LAST_NAMES_HE)
    phone = f"05{rng.choice('0234578')}-{rng.randrange(10**7):07d}" if has_phone else ""
    email = f"{rng.choice(EMAIL_SLUGS)}{i}@example.com" if has_email else ""
    contact_options = {"whatsapp": 45, "phone": 35, "email": 20} if has_phone else {"email": 1}
    preferred_contact = _pick(rng, contact_options)
    business = event_type in ("חגיגה פרטית", "אחר") and rng.random() < 0.35 or rng.random() < 0.05
    company = rng.choice(COMPANY_NAMES) if business else ""
    age_group = (
        _pick(rng, {"18-24": 6, "25-34": 24, "35-44": 32, "45-54": 22, "55-64": 11, "65+": 5})
        if rng.random() < 0.6
        else ""  # optional field, often skipped
    )
    residence = city if fulfillment == "delivery" and rng.random() < 0.8 else rng.choice(CITIES)
    past_customer = returning and rng.random() < 0.35 or rng.random() < 0.04
    past_orders = _lognormal_int(rng, 1.5, 0.5, 1, 12) if past_customer else 0
    past_spend = round(past_orders * rng.uniform(1500, 6000)) if past_customer else 0
    consent = rng.random() < 0.45
    callback = has_phone and rng.random() < 0.3
    budget = round(rng.lognormvariate(math.log(110), 0.35)) if rng.random() < 0.45 else ""
    kashrut = _pick(rng, {"none": 35, "kosher": 50, "mehadrin": 15})
    venue = (
        _pick(rng, {"office": 75, "hall": 15, "outdoor": 10})
        if business
        else _pick(rng, {"home": 60, "hall": 18, "synagogue": 10, "outdoor": 12})
    )

    e = TRUE_EFFECTS
    logit = (
        e["intercept"]
        + e["event_type"].get(event_type, 0.0)
        + (e["lead_days_short"] if days_until < 4 else 0.0)
        + (e["lead_days_far"] if days_until > 90 else 0.0)
        + e["log_guests"] * math.log1p(total)
        + e["has_phone"] * has_phone
        + e["has_notes"] * (notes_length > 0)
        + e["log_time_on_site"] * (math.log(time_on_site) - math.log(240))
        + e["pages_viewed"] * pages
        + e["returning_visitor"] * returning
        + e["used_ai_chat"] * used_ai
        + e["has_draft"] * (dishes > 0)
        + e["traffic_source"].get(source, 0.0)
        + e["device_mobile"] * (device == "mobile")
        + (e["night_visit"] if hour < 6 else 0.0)
        + e["browser_language"].get(lang, 0.0)
        + (e["bot_like_form"] if form_fill < 15 else 0.0)
        + e["business_customer"] * business
        + e["past_customer"] * past_customer
        + e["requested_callback"] * callback
        + (e["budget_stated"] if budget != "" else 0.0)
        + (e["budget_low"] if budget != "" and budget < 70 else 0.0)
        + e["kashrut"].get(kashrut, 0.0)
        + e["contact_whatsapp"] * (preferred_contact == "whatsapp")
        + e["marketing_consent"] * consent
    )
    purchased = rng.random() < 1 / (1 + math.exp(-logit))

    return {
        "lead_id": f"L{i:06d}",
        "created_at": created.isoformat(timespec="minutes"),
        "full_name": f"{first} {last}",
        "phone": phone,
        "email": email,
        "preferred_contact": preferred_contact,
        "customer_type": "business" if business else "private",
        "company_name": company,
        "age_group": age_group,
        "residence_city": residence,
        "is_past_customer": int(past_customer),
        "past_orders": past_orders,
        "past_spend_ils": past_spend,
        "marketing_consent": int(consent),
        "requested_callback": int(callback),
        "budget_per_guest_ils": budget,
        "kashrut": kashrut,
        "venue_type": venue,
        "event_type": event_type,
        "event_date": event_date.isoformat(),
        "days_until_event": days_until,
        "slot": rng.choice(SLOTS[fulfillment]),
        "fulfillment": fulfillment,
        "city": city,
        "adults": adults,
        "children": children,
        "vegetarian": vegetarian,
        "vegan": vegan,
        "restricted": restricted,
        "notes_length": notes_length,
        "has_phone": int(has_phone),
        "has_email": int(has_email),
        "device": device,
        "browser": browser,
        "os": os_name,
        "browser_language": lang,
        "visit_hour": hour,
        "visit_weekday": created.isoweekday() % 7,  # 0 = Sunday, Israeli week start
        "traffic_source": source,
        "time_on_site_sec": time_on_site,
        "pages_viewed": pages,
        "viewed_menu": int(viewed_menu),
        "form_fill_sec": form_fill,
        "returning_visitor": int(returning),
        "previous_visits": previous_visits,
        "used_ai_chat": int(used_ai),
        "ai_messages": ai_messages,
        "dishes_in_draft": dishes,
        "draft_total_ils": draft_total,
        "purchased": int(purchased),
    }


def generate(rows: int, seed: int, start: date = date(2025, 1, 1)) -> list[dict]:
    rng = random.Random(seed)  # noqa: S311  synthetic data, not security-sensitive
    t0 = datetime.combine(start, datetime.min.time())
    leads = [make_lead(rng, i + 1, t0) for i in range(rows)]
    leads.sort(key=lambda r: r["created_at"])  # time order, for a time-based train/test split
    for n, r in enumerate(leads, 1):
        r["lead_id"] = f"L{n:06d}"
    return leads


def write_csv(leads: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel shows Hebrew
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(leads)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--rows", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--out", type=Path, default=Path(__file__).parent / "data" / "leads_synthetic.csv"
    )
    args = p.parse_args()
    leads = generate(args.rows, args.seed)
    write_csv(leads, args.out)
    rate = sum(r["purchased"] for r in leads) / len(leads)
    print(f"wrote {len(leads)} leads to {args.out} (purchase rate {rate:.1%})")


if __name__ == "__main__":
    main()
