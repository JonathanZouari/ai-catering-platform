from fastapi.testclient import TestClient

from app.api.dishes import get_db
from app.db import connect, seed
from app.main import app


def test_list_dishes(tmp_path):
    path = str(tmp_path / "t.db")
    seed.seed(path)
    app.dependency_overrides[get_db] = lambda: connect(path)
    try:
        data = TestClient(app).get("/api/dishes").json()
    finally:
        app.dependency_overrides.clear()
    assert len(data) == len(seed.DISHES)
    lasagna = next(d for d in data if d["name"] == "לזניה גבינות")
    assert lasagna["kashrut_class"] == "dairy"
    assert {"name": "חלב", "status": "contains"} in lasagna["allergens"]
