"""Create a pilot caterer by hand.

First create the caterer's login in Supabase (Authentication → Users), then run:

    uv run python -m scripts.create_caterer --slug my-caterer --name "השם" --auth-user-id <uuid>
"""

import argparse

from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.schemas.caterers import CatererCreate
from app.services.caterers import create_caterer


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a caterer and link its first login.")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--auth-user-id", required=True)
    args = parser.parse_args()

    data = CatererCreate(slug=args.slug, name=args.name, auth_user_id=args.auth_user_id)
    with Session(get_engine(), expire_on_commit=False) as session:
        caterer = create_caterer(session, data)
    print(f"Created {caterer.slug} ({caterer.id}): /c/{caterer.slug}/")


if __name__ == "__main__":
    main()
