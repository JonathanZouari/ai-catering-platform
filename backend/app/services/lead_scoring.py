"""Local synthetic logistic-regression inference. Not exposed as a production API."""

import json
import math
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class WebsiteInquiry(BaseModel):
    """Initial submission only; no outcome or post-contact features accepted."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    guest_count: int = Field(ge=10, le=250, strict=True)
    days_until_event: int | None = Field(default=None, ge=2, le=180, strict=True)
    budget_per_guest: float | None = Field(default=None, ge=40, le=280)


def score_demo(inquiry: WebsiteInquiry) -> dict:
    model = json.loads(
        (Path(__file__).parents[1] / "models/lead_demo_logistic.json").read_text("utf-8")
    )
    values = [
        inquiry.guest_count,
        inquiry.days_until_event or 0,
        inquiry.budget_per_guest or 0,
        int(inquiry.days_until_event is not None),
        int(inquiry.budget_per_guest is not None),
    ]
    logit = model["intercept"] + sum(
        coefficient * (value - mean) / scale
        for value, mean, scale, coefficient in zip(
            values, model["mean"], model["scale"], model["coefficients"], strict=True
        )
    )
    probability = 1 / (1 + math.exp(-logit))
    return {
        "synthetic_only": True,
        "model_version": model["version"],
        "demo_probability": probability,
        "demo_class": "higher" if probability >= model["threshold"] else "lower",
        "target": model["target"],
    }
