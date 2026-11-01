from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def valid_inquiry(**overrides):
    body = {
        "name": "Dana Levi",
        "email": "dana@example.com",
        "phone": "+972 50 123 4567",
        "event_type": "birthday",
        "event_date": (date.today() + timedelta(days=30)).isoformat(),
        "guests": 40,
        "fulfillment": "delivery",
        "notes": "Two vegan guests",
    }
    return body | overrides


def test_create_inquiry():
    response = client.post("/api/inquiries", json=valid_inquiry())
    assert response.status_code == 201
    assert response.json() == {"status": "received"}


def test_optional_fields_may_be_null():
    response = client.post("/api/inquiries", json=valid_inquiry(phone=None, notes=None))
    assert response.status_code == 201


def test_rejects_invalid_inquiries():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    for overrides in (
        {"name": "   "},
        {"email": "not-an-email"},
        {"event_type": "corporate"},
        {"event_date": yesterday},
        {"guests": 0},
        {"fulfillment": "on_site"},
    ):
        response = client.post("/api/inquiries", json=valid_inquiry(**overrides))
        assert response.status_code == 422, overrides


def test_landing_page_served():
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="inquiry-form"' in response.text
