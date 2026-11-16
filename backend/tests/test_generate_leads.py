import csv

from ml.generate_leads import FIELDS, generate, write_csv


def test_generate_is_deterministic_and_plausible(tmp_path):
    leads = generate(3000, seed=7)
    assert leads == generate(3000, seed=7)
    assert all(set(r) == set(FIELDS) for r in leads)

    rate = sum(r["purchased"] for r in leads) / len(leads)
    assert 0.08 < rate < 0.35

    for r in leads:
        assert r["days_until_event"] >= 2
        assert r["adults"] >= 1
        assert r["city"] == "" or r["fulfillment"] == "delivery"
        assert (r["dishes_in_draft"] == 0) == (r["draft_total_ils"] == 0)
        assert r["email"] == "" or r["email"].endswith("@example.com")
        assert bool(r["phone"]) == bool(r["has_phone"])
        assert r["is_past_customer"] or r["past_orders"] == 0

    # hidden effect is recoverable: leads with a draft order buy more often
    def rate_of(rows):
        return sum(r["purchased"] for r in rows) / len(rows)

    assert rate_of([r for r in leads if r["dishes_in_draft"]]) > rate_of(
        [r for r in leads if not r["dishes_in_draft"]]
    )

    out = tmp_path / "leads.csv"
    write_csv(leads[:10], out)
    with out.open(encoding="utf-8-sig") as f:
        assert len(list(csv.DictReader(f))) == 10
