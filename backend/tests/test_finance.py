import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.db.money import from_minor, to_minor
from app.repositories.finance import order_balance, record_receipt, record_refund

IntegrityError = sqlite3.IntegrityError
WHEN = datetime(2026, 11, 2, 9, 30, tzinfo=UTC)


# --- money helpers ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "minor"),
    [(Decimal("0.10"), 10), ("0.2", 20), ("1234.56", 123456), (7, 700), ("-3.5", -350)],
)
def test_to_minor_is_exact(amount, minor):
    assert to_minor(amount) == minor


def test_no_float_drift():
    total = sum(to_minor(x) for x in ["0.1", "0.2"])
    assert from_minor(total) == Decimal("0.30")


@pytest.mark.parametrize("bad", [0.1, True, None])
def test_to_minor_rejects_floats_and_non_numbers(bad):
    with pytest.raises(TypeError):
        to_minor(bad)


@pytest.mark.parametrize("bad", ["1.005", "NaN", "Infinity", "abc"])
def test_to_minor_rejects_sub_cent_and_invalid(bad):
    with pytest.raises(ValueError):
        to_minor(bad)


# --- receipts and refunds --------------------------------------------------------------------


def test_receipts_refunds_and_balance(conn, make):
    order_id = make.priced_order(total_minor=250_000)  # 2,500.00
    deposit = record_receipt(
        conn,
        order_id=order_id,
        amount="1000.00",
        method="bank_transfer",
        occurred_at=WHEN,
        document_number="R-1",
    )
    record_receipt(
        conn,
        order_id=order_id,
        amount=Decimal("1500.00"),
        method="credit_card",
        occurred_at=WHEN,
        document_number="R-2",
    )
    record_refund(
        conn,
        receipt_id=deposit,
        amount="199.99",
        method="bank_transfer",
        reason="guest count reduced",
        occurred_at=WHEN,
        document_number="C-1",
    )

    balance = order_balance(conn, order_id)
    assert balance.currency == "ILS"
    assert balance.total == Decimal("2500.00")
    assert balance.received == Decimal("2500.00")
    assert balance.refunded == Decimal("199.99")
    assert balance.net_paid == Decimal("2300.01")
    assert balance.balance_due == Decimal("199.99")


def test_refunds_cannot_exceed_receipt(conn, make):
    order_id = make.priced_order()
    receipt = record_receipt(
        conn, order_id=order_id, amount="100.00", method="cash", occurred_at=WHEN
    )
    record_refund(
        conn, receipt_id=receipt, amount="60.00", method="cash", reason="partial", occurred_at=WHEN
    )
    with pytest.raises(IntegrityError, match="refunds exceed the original receipt"):
        record_refund(
            conn,
            receipt_id=receipt,
            amount="40.01",
            method="cash",
            reason="again",
            occurred_at=WHEN,
        )
    record_refund(
        conn, receipt_id=receipt, amount="40.00", method="cash", reason="rest", occurred_at=WHEN
    )


def test_refund_of_a_refund_is_rejected(conn, make):
    order_id = make.priced_order()
    receipt = record_receipt(conn, order_id=order_id, amount="100", method="cash", occurred_at=WHEN)
    refund = record_refund(
        conn, receipt_id=receipt, amount="10", method="cash", reason="x", occurred_at=WHEN
    )
    with pytest.raises(IntegrityError, match="must reference a receipt"):
        record_refund(
            conn, receipt_id=refund, amount="1", method="cash", reason="y", occurred_at=WHEN
        )


def test_refund_must_stay_on_receipts_order(conn, make):
    order_a, order_b = make.priced_order(), make.priced_order()
    receipt = record_receipt(conn, order_id=order_a, amount="100", method="cash", occurred_at=WHEN)
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        make.insert(
            "payments",
            kind="refund",
            order_id=order_b,
            currency="ILS",
            amount_minor=100,
            method="cash",
            refund_of_payment_id=receipt,
            reason="wrong order",
            occurred_at="2026-11-02T09:30:00Z",
        )


def test_payment_currency_must_match_order(make):
    order_id = make.priced_order()
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        make.insert(
            "payments",
            kind="receipt",
            order_id=order_id,
            currency="USD",
            amount_minor=100,
            method="cash",
            occurred_at="2026-11-02T09:30:00Z",
        )


def test_refund_requires_reason_and_link(make):
    order_id = make.priced_order()
    base = {
        "order_id": order_id,
        "currency": "ILS",
        "amount_minor": 100,
        "method": "cash",
        "occurred_at": "2026-11-02T09:30:00Z",
    }
    with pytest.raises(IntegrityError, match="must reference a receipt"):
        make.insert("payments", kind="refund", **base)  # no receipt link
    receipt = make.insert("payments", kind="receipt", **base)
    with pytest.raises(IntegrityError, match="CHECK"):
        make.insert("payments", kind="refund", refund_of_payment_id=receipt, **base)  # no reason


@pytest.mark.parametrize("amount_minor", [0, -500])
def test_amount_must_be_positive(make, amount_minor):
    with pytest.raises(IntegrityError, match="CHECK"):
        make.insert(
            "payments",
            kind="receipt",
            order_id=make.priced_order(),
            currency="ILS",
            amount_minor=amount_minor,
            method="cash",
            occurred_at="2026-11-02T09:30:00Z",
        )


def test_document_numbers_unique(conn, make):
    order_id = make.priced_order()
    record_receipt(
        conn, order_id=order_id, amount="1", method="cash", occurred_at=WHEN, document_number="R-9"
    )
    with pytest.raises(IntegrityError, match="UNIQUE"):
        record_receipt(
            conn,
            order_id=order_id,
            amount="1",
            method="cash",
            occurred_at=WHEN,
            document_number="R-9",
        )


def test_payments_are_append_only(conn, make):
    receipt = record_receipt(
        conn, order_id=make.priced_order(), amount="100", method="cash", occurred_at=WHEN
    )
    with pytest.raises(IntegrityError, match="append-only"):
        conn.execute("UPDATE payments SET amount_minor = 1 WHERE id = ?", (receipt,))
    with pytest.raises(IntegrityError, match="append-only"):
        conn.execute("DELETE FROM payments WHERE id = ?", (receipt,))


def test_order_with_payments_cannot_change_currency(conn, make):
    order_id = make.priced_order()
    record_receipt(conn, order_id=order_id, amount="1", method="cash", occurred_at=WHEN)
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        conn.execute("UPDATE orders SET currency = 'USD' WHERE id = ?", (order_id,))
