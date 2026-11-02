from tests.conftest import AUTH

SLOT = {"fulfillment_type": "pickup", "weekday": 0, "start_time": "10:00", "end_time": "12:00"}


def test_admin_availability_requires_token(client):
    assert client.get("/api/admin/blocked-dates").status_code == 401
    assert client.post("/api/admin/time-slots", json=SLOT).status_code == 401


def test_block_and_unblock_date(client):
    res = client.post(
        "/api/admin/blocked-dates", json={"date": "2026-12-25", "reason": " חופשה "}, headers=AUTH
    )
    assert res.status_code == 201, res.text
    blocked = res.json()
    assert blocked["reason"] == "חופשה"
    dup = client.post("/api/admin/blocked-dates", json={"date": "2026-12-25"}, headers=AUTH)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "conflict"
    assert (
        client.delete(f"/api/admin/blocked-dates/{blocked['id']}", headers=AUTH).status_code == 204
    )
    assert client.get("/api/admin/blocked-dates", headers=AUTH).json() == []


def test_time_slot_crud_and_order_check(client):
    res = client.post("/api/admin/time-slots", json=SLOT, headers=AUTH)
    assert res.status_code == 201, res.text
    slot = res.json()
    assert slot["start_time"] == "10:00:00" and slot["capacity"] is None
    bad = client.post("/api/admin/time-slots", json={**SLOT, "end_time": "09:00"}, headers=AUTH)
    assert bad.status_code == 422
    assert (
        client.post("/api/admin/time-slots", json={**SLOT, "weekday": 7}, headers=AUTH).status_code
        == 422
    )
    # A PATCH that would invert the slot is rejected and leaves it unchanged.
    url = f"/api/admin/time-slots/{slot['id']}"
    assert client.patch(url, json={"start_time": "13:00"}, headers=AUTH).status_code == 422
    assert client.patch(url, json={"is_active": None}, headers=AUTH).status_code == 422
    res = client.patch(url, json={"weekday": None, "capacity": 5}, headers=AUTH)
    assert res.json()["weekday"] is None and res.json()["start_time"] == "10:00:00"
    assert client.delete(url, headers=AUTH).status_code == 204
    assert client.delete(url, headers=AUTH).status_code == 404


def test_public_availability(client):
    for d in ("2026-12-01", "2026-12-20", "2027-02-01"):
        client.post("/api/admin/blocked-dates", json={"date": d, "reason": "פרטי"}, headers=AUTH)
    client.post("/api/admin/time-slots", json=SLOT, headers=AUTH)
    client.post("/api/admin/time-slots", json={**SLOT, "is_active": False}, headers=AUTH)

    res = client.get("/api/availability?from=2026-12-01&to=2026-12-31")
    assert res.status_code == 200
    body = res.json()
    assert body["blocked_dates"] == ["2026-12-01", "2026-12-20"]  # reason not exposed
    assert len(body["time_slots"]) == 1 and "capacity" not in body["time_slots"][0]

    assert client.get("/api/availability?from=2026-12-31&to=2026-12-01").status_code == 422
    assert client.get("/api/availability?from=2026-01-01&to=2027-06-01").status_code == 422
    assert client.get("/api/availability").status_code == 422
