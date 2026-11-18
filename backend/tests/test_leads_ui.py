import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
DEMO = Path(__file__).resolve().parents[2] / "frontend" / "admin" / "leads" / "demo-leads.json"
STAGES = {"new", "contacted", "quoted", "negotiating", "won", "lost"}


def test_leads_page_and_assets_are_served():
    page = client.get("/admin/leads/")
    assert page.status_code == 200
    assert 'dir="rtl"' in page.text and "/js/admin/leads.js" in page.text
    assert client.get("/js/admin/leads.js").status_code == 200
    assert client.get("/css/leads.css").status_code == 200


def test_demo_leads_are_synthetic_and_consistent():
    leads = json.loads(DEMO.read_text(encoding="utf-8"))
    assert len(leads) >= 20
    for lead in leads:
        assert lead["stage"] in STAGES
        assert 0 <= lead["score"] <= 1
        expected = "high" if lead["score"] >= 0.55 else "medium" if lead["score"] >= 0.3 else "low"
        assert lead["band"] == expected
        assert lead["name"].startswith("ליד לדוגמה")  # placeholder names, never real people
        assert "phone" not in lead and "email" not in lead


def test_demo_model_metrics_are_complete():
    path = DEMO.with_name("demo-models.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    names = {m["name"] for m in data["models"]}
    assert {"base_rate", "logreg", "random_forest", "hist_gb"} <= names
    assert data["best"] in names - {"base_rate"}
    for m in data["models"]:
        assert 0 <= m["roc_auc"] <= 1 and 0 <= m["pr_auc"] <= 1 and 0 <= m["brier"] <= 1
    assert len(data["calibration"]) == 5
    assert client.get("/admin/leads/demo-models.json").status_code == 200
