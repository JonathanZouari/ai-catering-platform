"""Build frontend/data/cities.json: the Hebrew names of every Israeli locality, for the city field.

Source: the Central Bureau of Statistics locality list on data.gov.il ("רשימת ישובים", dataset
citiesandsettelments, open licence). Bedouin tribe entries ("(שבט)") and catch-all rows are left
out. Run it again when the CBS list changes:  python tools/build_cities.py
"""

import json
import re
import urllib.request
from pathlib import Path

URL = (
    "https://data.gov.il/api/3/action/datastore_search"
    "?resource_id=5c78e9fa-c2e2-4771-93ff-7f400a12f7ba&limit=5000"
)
OUT = Path(__file__).resolve().parents[1] / "frontend" / "data" / "cities.json"
SKIP = ("שבט", "שאר ישוב", "לא רשום")


def clean(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def build(records: list[dict]) -> list[str]:
    names = {clean(r["שם_ישוב"]) for r in records}
    return sorted(n for n in names if n and not any(s in n for s in SKIP))


def main() -> None:
    req = urllib.request.Request(URL, headers={"User-Agent": "yummai-build-cities"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - fixed https URL
        result = json.load(resp)["result"]
    records = result["records"]
    if len(records) != result["total"]:
        raise SystemExit(f"got {len(records)} of {result['total']} records; raise the limit")
    cities = build(records)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cities, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"{len(cities)} localities written to {OUT}")


if __name__ == "__main__":
    main()
