"""Lead storage in files. Demo leads ship in data/leads_open.csv; leads from the form are
appended to data/runtime/leads.jsonl, which is git-ignored because it holds real contact details."""

import csv
import json
import threading
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEMO_FILE = DATA_DIR / "leads_open.csv"
RUNTIME_FILE = DATA_DIR / "runtime" / "leads.jsonl"
MAX_RUNTIME_BYTES = 5_000_000  # stop accepting before a flood fills the disk

_lock = threading.Lock()


class StorageFull(Exception):
    pass


def demo_leads(path: Path = DEMO_FILE) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [{**row, "is_demo": True} for row in csv.DictReader(f)]


def form_leads(path: Path = RUNTIME_FILE) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    today = date.today()
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        # Days left are recounted each time, so the score ages with the lead.
        row["days_until_event"] = max(0, (date.fromisoformat(row["event_date"]) - today).days)
        out.append({**row, "is_demo": False})
    return out


def add_lead(lead: dict[str, Any], path: Path = RUNTIME_FILE) -> str:
    lead_id = f"W-{uuid.uuid4().hex[:8]}"
    record = {**lead, "lead_id": lead_id, "created_at": datetime.now(UTC).isoformat()}
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size + len(line) > MAX_RUNTIME_BYTES:
            raise StorageFull
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    return lead_id
