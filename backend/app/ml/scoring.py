"""Load a trained artifact and score leads. Used by the future lead-scoring service; advisory output
only."""

from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd

from app.ml.features import FEATURES, build_features


@dataclass(frozen=True)
class Score:
    probability: float  # P(won), rounded to 4 places to fit numeric(5,4)
    label: str  # 'won' | 'lost' at the artifact's threshold
    model_version: str


def load_artifact(path: str | Path) -> dict:
    """Load an artifact from app.ml.train. Load only our own files (joblib = pickle)."""
    artifact = joblib.load(path)
    if artifact.get("features") != FEATURES:
        raise ValueError(
            "artifact was trained with a different feature list; retrain or update the code"
        )
    return artifact


def score_rows(artifact: dict, rows: pd.DataFrame) -> list[Score]:
    """`rows` has the raw view columns (see features.RAW_COLUMNS), one row per lead."""
    proba = artifact["model"].predict_proba(build_features(rows))[:, 1]
    threshold = artifact["threshold"]
    return [
        Score(round(float(p), 4), "won" if p >= threshold else "lost", artifact["version"])
        for p in proba
    ]
