import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents import tools
from app.agents.client import LLMClient, LLMError
from app.agents.prompt import build_system_prompt
from app.core.errors import AppError
from app.core.tenancy import CatererScope
from app.models.enums import ProposalStatus
from app.schemas.ai import ChatReply, ProposalOut
from app.services import assistant, proposals

logger = logging.getLogger(__name__)

MAX_STEPS = 8
HISTORY_MESSAGES = 20
FALLBACK_REPLY = "לא הצלחתי לענות על זה. אפשר לנסח אחרת, או להמשיך בתפריט."


def _text(content: list) -> str:
    return "".join(block.text for block in content if block.type == "text").strip()


def _run_tools(context: tools.ToolContext, response, messages: list[dict]) -> None:
    results = []
    for block in response.content:
        if block.type != "tool_use":
            continue
        output, is_error = tools.run_tool(context, block.name, block.input)
        logger.info("ai tool %s order=%s error=%s", block.name, context.order_id, is_error)
        results.append(
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
                "is_error": is_error,
            }
        )
    messages.append({"role": "user", "content": results})


def _answer(llm: LLMClient, context: tools.ToolContext, system: str, messages: list[dict]) -> str:
    definitions = tools.definitions()
    for _ in range(MAX_STEPS):
        # No transaction stays open while waiting for the provider.
        context.session.commit()
        try:
            response = llm.create(system, definitions, messages)
        except LLMError as error:
            logger.warning("ai provider failed order=%s: %s", context.order_id, error)
            raise AppError(503, "ai_failed", "העוזר לא הצליח לענות. נסו שוב עוד מעט") from error

        # A cut-off or declined turn can hold a partial tool call, which must never run.
        if response.stop_reason in ("refusal", "max_tokens"):
            return FALLBACK_REPLY
        if response.stop_reason != "tool_use":
            return _text(response.content) or FALLBACK_REPLY
        messages.append({"role": "assistant", "content": response.content})
        _run_tools(context, response, messages)
    return FALLBACK_REPLY


def run_chat(
    session: Session,
    scope: CatererScope,
    order_id: UUID,
    message: str,
    llm: LLMClient | None,
) -> ChatReply:
    if llm is None:
        raise AppError(503, "ai_unavailable", "העוזר אינו זמין כרגע. אפשר להמשיך בתפריט")
    assistant.require_draft(session, scope, order_id)
    assistant.consume_allowance(session, scope, order_id)

    conversation = assistant.open_conversation(session, scope, order_id)
    past = assistant.recent_messages(session, scope, conversation.id, HISTORY_MESSAGES)
    messages = [{"role": item.role, "content": item.content["text"]} for item in past]
    messages.append({"role": "user", "content": message})

    context = tools.ToolContext(session, scope, order_id, conversation.id)
    system = build_system_prompt(assistant.caterer_name(session, scope))
    reply = _answer(llm, context, system, messages)

    assistant.save_exchange(session, scope, conversation.id, message, reply)
    pending = proposals.list_proposals(session, scope, order_id, ProposalStatus.PENDING)
    return ChatReply(reply=reply, proposals=[ProposalOut.model_validate(p) for p in pending])
