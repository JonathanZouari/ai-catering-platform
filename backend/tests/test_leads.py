"""The leads endpoint, with Supabase replaced by a stand-in that records what it was asked."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.supabase import get_supabase
from app.main import app
from app.services.lead_scoring import purchase_probability

LEADS = "/api/admin/leads"
AUTH = {"Authorization": "Bearer user-token"}


def lead(number: int, status: str, **changes) -> dict:
    """A lead as Supabase's REST API returns it."""
    return {
        "id": f"00000000-0000-4000-8000-{number:012d}",
        "full_name": f"ליד {number}",
        "phone": "050-555-0000",
        "email": None,
        "event_type": "יום הולדת",
        "event_date": "2026-12-20",
        "guests": 50,
        "budget_per_guest": 200.0,
        "source": "google",
        "is_returning": False,
        "status": status,
        "created_at": "2026-11-10T08:30:00.123456+00:00",
        **changes,
    }


@pytest.fixture
def supabase():
    """Stand-in for Supabase. Set `.reply` to the response; read `.requests` afterwards."""

    class FakeSupabase:
        reply = httpx.Response(200, json=[])
        requests: list[httpx.Request] = []

        def handle(self, request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            if isinstance(self.reply, Exception):
                raise self.reply
            return self.reply

    fake = FakeSupabase()
    fake.requests = []
    client = httpx.Client(
        base_url="https://project.supabase.co",
        headers={"apikey": "publishable-key"},
        transport=httpx.MockTransport(fake.handle),
    )
    app.dependency_overrides[get_supabase] = lambda: client
    yield fake
    app.dependency_overrides.clear()


def test_request_without_a_token_is_refused_before_supabase_is_asked(supabase):
    assert TestClient(app).get(LEADS).status_code == 401
    assert supabase.requests == []


def test_callers_own_token_is_passed_on_with_the_publishable_key(supabase):
    assert TestClient(app).get(LEADS, headers=AUTH).status_code == 200
    (request,) = supabase.requests
    assert request.url.path == "/rest/v1/leads"
    assert request.headers["authorization"] == "Bearer user-token"
    assert request.headers["apikey"] == "publishable-key"


def test_user_who_is_not_the_admin_gets_no_leads(supabase):
    # Row level security answers a non-admin with an empty list.
    supabase.reply = httpx.Response(200, json=[])
    response = TestClient(app).get(LEADS, headers=AUTH)
    assert response.status_code == 200
    assert response.json() == []


def test_open_leads_come_first_by_probability_then_closed_leads(supabase):
    supabase.reply = httpx.Response(
        200,
        json=[
            lead(1, "won", is_returning=True),
            lead(2, "new", source="instagram"),
            lead(3, "quoted", source="referral", is_returning=True),
            lead(4, "lost"),
            lead(5, "contacted"),
        ],
    )
    leads = TestClient(app).get(LEADS, headers=AUTH).json()

    assert [item["status"] for item in leads] == ["quoted", "contacted", "new", "won", "lost"]
    open_probabilities = [item["purchase_probability"] for item in leads[:3]]
    assert open_probabilities == sorted(open_probabilities, reverse=True)
    assert all(0 < item["purchase_probability"] < 1 for item in leads)


def test_probability_uses_the_days_between_inquiry_and_event(supabase):
    supabase.reply = httpx.Response(200, json=[lead(1, "new")])
    (item,) = TestClient(app).get(LEADS, headers=AUTH).json()
    # Inquiry on 10 November, event on 20 December: 40 days.
    expected = purchase_probability({**lead(1, "new"), "lead_days": 40})
    assert item["purchase_probability"] == pytest.approx(expected)


@pytest.mark.parametrize(
    "reply, expected_status",
    [
        (httpx.Response(401, json={"message": "JWT expired"}), 401),
        (httpx.Response(403, json={"message": "permission denied"}), 401),
        (httpx.Response(404, json={"code": "PGRST205"}), 502),
        (httpx.Response(500), 502),
        (httpx.ConnectError("no route"), 502),
    ],
)
def test_supabase_failure_is_reported_without_its_details(supabase, reply, expected_status):
    supabase.reply = reply
    response = TestClient(app).get(LEADS, headers=AUTH)
    assert response.status_code == expected_status
    assert set(response.json()) == {"detail"}
    assert "JWT" not in response.text and "PGRST" not in response.text


def test_missing_supabase_settings_answer_503(monkeypatch):
    monkeypatch.setattr("app.core.supabase.get_settings", lambda: Settings(_env_file=None))
    assert TestClient(app).get(LEADS, headers=AUTH).status_code == 503
