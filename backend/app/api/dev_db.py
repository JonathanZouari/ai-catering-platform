"""Read-only database viewer API. Development only (404 in any other APP_ENV)."""

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.sqlite_db import connect, migrate

router = APIRouter(prefix="/api/dev/db", tags=["dev"])


def _conn():
    if get_settings().app_env != "development":
        raise HTTPException(404)
    conn = connect()
    migrate(conn)
    return conn


@router.get("/tables")
def list_tables() -> list[dict]:
    with _conn() as c:
        names = [
            r[0]
            for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return [
            {"name": n, "rows": c.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]}  # noqa: S608
            for n in names
        ]


@router.get("/tables/{name}")
def table_detail(name: str) -> dict:
    with _conn() as c:
        known = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if name not in known:  # whitelist: never interpolate unvalidated input
            raise HTTPException(404, "unknown table")
        cols = [
            {
                "name": r["name"],
                "type": r["type"],
                "notnull": bool(r["notnull"]),
                "pk": bool(r["pk"]),
                "default": r["dflt_value"],
            }
            for r in c.execute(f'PRAGMA table_info("{name}")')
        ]
        fks = [
            {"column": r["from"], "references": f"{r['table']}.{r['to']}"}
            for r in c.execute(f'PRAGMA foreign_key_list("{name}")')
        ]
        rows = [list(r) for r in c.execute(f'SELECT * FROM "{name}" LIMIT 200')]  # noqa: S608
        return {"name": name, "columns": cols, "foreign_keys": fks, "rows": rows}
