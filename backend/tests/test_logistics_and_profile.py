import pytest

from app.core.config import get_settings
from tests.test_catalog import PDF, PNG


@pytest.fixture
def tenant(make_tenant):
    return make_tenant("caterer-a")


ZONES = "/api/admin/delivery-zones"
SLOTS = "/api/admin/time-slots"
BLOCKED = "/api/admin/blocked-dates"
PROFILE = "/api/admin/profile"
ZONE = {"name": "מרכז", "fee": "50.00", "cities": ["תל אביב", "רמת גן"]}
SLOT = {"fulfillment_type": "pickup", "weekday": 4, "start_time": "09:00", "end_time": "12:00"}


def test_zone_lifecycle(client, tenant):
    zone = client.post(ZONES, json=ZONE, headers=tenant.headers).json()
    assert zone["cities"] == ["תל אביב", "רמת גן"]
    url = f"{ZONES}/{zone['id']}"

    updated = client.patch(url, json={"cities": ["חיפה"]}, headers=tenant.headers).json()
    assert updated["cities"] == ["חיפה"]
    assert updated["fee"] == "50.00"

    assert client.delete(url, headers=tenant.headers).status_code == 204
    assert client.get(ZONES, headers=tenant.headers).json() == []


def test_zone_name_conflict(client, tenant):
    client.post(ZONES, json=ZONE, headers=tenant.headers)
    assert client.post(ZONES, json=ZONE, headers=tenant.headers).status_code == 409


@pytest.mark.parametrize("change", [{"cities": []}, {"fee": "-1"}, {"cities": [""]}])
def test_invalid_zone_is_rejected(client, tenant, change):
    assert client.post(ZONES, json=ZONE | change, headers=tenant.headers).status_code == 422


def test_slot_lifecycle(client, tenant):
    slot = client.post(SLOTS, json=SLOT, headers=tenant.headers).json()
    assert slot["start_time"] == "09:00:00"
    url = f"{SLOTS}/{slot['id']}"

    updated = client.patch(url, json={"capacity": 3}, headers=tenant.headers).json()
    assert updated["capacity"] == 3

    assert client.delete(url, headers=tenant.headers).status_code == 204


@pytest.mark.parametrize(
    "change", [{"end_time": "08:00"}, {"end_time": "09:00"}, {"weekday": 7}, {"capacity": -1}]
)
def test_invalid_slot_is_rejected(client, tenant, change):
    assert client.post(SLOTS, json=SLOT | change, headers=tenant.headers).status_code == 422


def test_patch_cannot_put_slot_end_before_start(client, tenant):
    slot = client.post(SLOTS, json=SLOT, headers=tenant.headers).json()
    url = f"{SLOTS}/{slot['id']}"

    response = client.patch(url, json={"end_time": "08:00"}, headers=tenant.headers)

    assert response.status_code == 422
    stored = client.get(SLOTS, headers=tenant.headers).json()[0]
    assert stored["end_time"] == "12:00:00"


def test_blocked_dates(client, tenant):
    body = {"date": "2027-04-22", "reason": "פסח"}
    blocked = client.post(BLOCKED, json=body, headers=tenant.headers)
    assert blocked.status_code == 201
    assert client.post(BLOCKED, json=body, headers=tenant.headers).status_code == 409

    url = f"{BLOCKED}/{blocked.json()['id']}"
    assert client.delete(url, headers=tenant.headers).status_code == 204


def test_profile_update(client, tenant):
    patch = {
        "name": "טעמים",
        "brand_color": "#7a4f2a",
        "kashrut_status": "כשר בהשגחת הרבנות",
        "kashrut_mixing_rule": "block",
    }
    profile = client.patch(PROFILE, json=patch, headers=tenant.headers).json()
    assert profile["kashrut_mixing_rule"] == "block"

    public = client.get(f"/api/c/{tenant.slug}").json()
    assert public["kashrut_status"] == "כשר בהשגחת הרבנות"
    assert "kashrut_mixing_rule" not in public


@pytest.mark.parametrize(
    "patch",
    [
        {"brand_color": "red"},
        {"kashrut_mixing_rule": "maybe"},
        {"name": None},
        {"kashrut_mixing_rule": None},
        {"slug": "stolen"},
        {"is_active": False},
    ],
)
def test_invalid_profile_update_is_rejected(client, tenant, patch):
    assert client.patch(PROFILE, json=patch, headers=tenant.headers).status_code == 422


def test_logo_rejects_pdf_but_certificate_accepts_it(client, tenant, storage):
    logo = client.post(f"{PROFILE}/logo", files={"file": ("x.pdf", PDF)}, headers=tenant.headers)
    assert logo.status_code == 422

    certificate = client.post(
        f"{PROFILE}/kashrut-certificate", files={"file": ("x.pdf", PDF)}, headers=tenant.headers
    ).json()
    assert certificate["kashrut_certificate_path"].startswith(f"{tenant.id}/certificates/")

    logo = client.post(
        f"{PROFILE}/logo", files={"file": ("x.png", PNG)}, headers=tenant.headers
    ).json()
    assert logo["logo_path"].startswith(f"{tenant.id}/logos/")


def test_client_config_never_exposes_the_service_key(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-secret")

    response = client.get("/api/config")
    get_settings.cache_clear()

    assert response.json()["supabase_anon_key"] == "anon-key"
    assert "service-secret" not in response.text
