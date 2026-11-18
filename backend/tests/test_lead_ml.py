import pytest

pytest.importorskip("numpy")
pytest.importorskip("sklearn")

from ml.synthetic import FIELDS, generate  # noqa: E402


def test_generator_is_deterministic_and_well_formed():
    a, b = generate(200, seed=1), generate(200, seed=1)
    assert a == b
    assert generate(200, seed=2) != a
    assert all(set(r) == set(FIELDS) for r in a)
    assert all(r["converted"] in (0, 1) and r["guests"] >= 4 for r in a)


def test_signal_is_recoverable():
    rows = generate(2000, seed=3)
    rate = {v: [r["converted"] for r in rows if r["repeat_customer"] == v] for v in (0, 1)}
    assert sum(rate[1]) / len(rate[1]) > sum(rate[0]) / len(rate[0])
