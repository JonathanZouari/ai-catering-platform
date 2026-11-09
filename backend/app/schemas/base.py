from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_validator


class InputModel(BaseModel):
    # extra="forbid": a body that tries to name a caterer is rejected, not ignored.
    model_config = ConfigDict(extra="forbid")


class PatchModel(InputModel):
    """Partial update. Fields in `required_fields` may be omitted but not set to null."""

    required_fields: ClassVar[set[str]] = set()

    @model_validator(mode="before")
    @classmethod
    def _reject_null_required(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for field in cls.required_fields:
                if field in data and data[field] is None:
                    raise ValueError(f"{field} cannot be null")
        return data


class OutputModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
