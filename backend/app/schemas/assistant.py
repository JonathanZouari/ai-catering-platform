from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.proposals import ProposalOut


class ChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ChatMessageOut(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatOut(BaseModel):
    available: bool  # configured and the daily limit isn't 0
    messages: list[ChatMessageOut]
    proposal: ProposalOut | None  # the assistant's open proposal, if any
    remaining_today: int
