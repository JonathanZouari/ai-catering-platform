"""Customer accounts: profile tied to a Supabase Auth user, and the customer's own orders.

Ownership is always resolved from the verified token (CustomerIdentity), never from request data.
Never link or look up accounts by email: customers.email is contact info, auth_user_id is identity.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.customer_auth import CustomerIdentity
from app.core.errors import AppError
from app.models.orders import Customer
from app.repositories import customers as repo
from app.schemas import customers as s


def me(db: Session, who: CustomerIdentity) -> s.MeOut:
    customer = repo.by_auth_user(db, who.user_id)
    return s.MeOut(
        email=who.email,
        profile=s.ProfileOut.model_validate(customer) if customer else None,
    )


def save_profile(db: Session, who: CustomerIdentity, data: s.ProfileIn) -> s.MeOut:
    customer = repo.by_auth_user(db, who.user_id)
    if customer is None:
        customer = Customer(auth_user_id=who.user_id)
        db.add(customer)
    customer.full_name = data.full_name
    customer.phone = data.phone
    customer.email = who.email  # the verified login email, not client input
    try:
        db.commit()
    except IntegrityError as exc:  # two first saves raced on auth_user_id
        db.rollback()
        raise AppError(409, "conflict", "Profile was just created; try again") from exc
    return me(db, who)


def my_orders(db: Session, who: CustomerIdentity) -> list[s.MyOrderOut]:
    customer = repo.by_auth_user(db, who.user_id)
    if customer is None:
        return []
    found = repo.orders_for(db, customer.id)
    pending = repo.with_pending_proposal(db, [o.id for o in found])
    return [
        s.MyOrderOut(
            id=o.id,
            status=o.status,
            event_type=o.event.event_type,
            event_date=o.event.event_date,
            guests=o.event.adults + o.event.children,
            total=o.total,
            submitted_at=o.submitted_at,
            decision_note=o.decision_note,
            has_pending_proposal=o.id in pending,
        )
        for o in found
    ]
