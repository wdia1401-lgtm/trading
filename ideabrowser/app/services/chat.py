"""Conversational AI analyst, grounded on a specific idea when one is attached."""

from sqlalchemy.orm import Session

from ..ai import get_provider
from ..models import ChatMessage, ChatSession
from .validation import idea_context

BASE_SYSTEM = (
    "You are the IdeaBrowser analyst: candid, data-grounded, and practical. "
    "Help the user validate, stress-test, and plan startup ideas. Prefer "
    "specific experiments over generic advice."
)


def _system_prompt(session: ChatSession) -> str:
    if session.idea is None:
        return BASE_SYSTEM
    idea = session.idea
    parts = [BASE_SYSTEM, "", "You are discussing this idea:", idea_context(idea)]
    report = idea.latest_report
    if report:
        dims = ", ".join(f"{k} {v:.0f}" for k, v in report.dimensions.items())
        parts.append(f"- Validation: {report.overall_score:.0f}/100 ({report.verdict}); {dims}")
    for fa in idea.framework_assessments:
        parts.append(f"- {fa.framework}: {fa.classification}")
    return "\n".join(parts)


def send_message(db: Session, session: ChatSession, content: str) -> ChatMessage:
    provider = get_provider()
    history = [{"role": m.role, "content": m.content} for m in session.messages]
    history.append({"role": "user", "content": content})

    db.add(ChatMessage(session_id=session.id, role="user", content=content))
    db.flush()
    answer = provider.chat(_system_prompt(session), history)

    reply = ChatMessage(session_id=session.id, role="assistant", content=answer)
    db.add(reply)
    db.flush()
    return reply
