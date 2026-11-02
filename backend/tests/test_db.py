from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.models.customer import Customer


def test_customer_saved_and_read_back():
    # In-memory DB: each test run starts empty and never touches yummai.db.
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add(Customer(full_name="דנה כהן", phone="050-1234567"))
        db.commit()

    with Session(engine) as db:
        saved = db.query(Customer).one()
        assert saved.full_name == "דנה כהן"
        assert saved.email is None
        assert saved.created_at is not None
