def test_list_dishes(client):
    data = client.get("/api/dishes").json()
    assert len(data) >= 11
    lasagna = next(d for d in data if d["name"] == "לזניה גבינות")
    assert lasagna["kashrut_class"] == "dairy"
    assert {"name": "חלב", "status": "contains"} in lasagna["allergens"]
