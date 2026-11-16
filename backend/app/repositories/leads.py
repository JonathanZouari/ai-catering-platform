import httpx

LEAD_COLUMNS = (
    "id,full_name,phone,email,event_type,event_date,guests,budget_per_guest,"
    "source,is_returning,status,created_at"
)


def list_leads(supabase: httpx.Client, access_token: str) -> list[dict]:
    """Every lead the token's user may read, newest first.

    Row level security lets only the admin read leads; any other signed-in user gets an
    empty list. Raises httpx.HTTPStatusError when Supabase refuses the request.
    """
    response = supabase.get(
        "/rest/v1/leads",
        params={"select": LEAD_COLUMNS, "order": "created_at.desc,id"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.json()
