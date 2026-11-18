from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("sklearn")

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "ml" / "dashboard.py"


def test_dashboard_renders_without_errors():
    at = AppTest.from_file(str(APP), default_timeout=240).run()
    assert not at.exception
    assert len(at.tabs) == 4
    assert len(at.dataframe) >= 4
