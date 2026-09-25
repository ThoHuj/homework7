"""In-memory session store for chat history and stream cancellation."""

import asyncio
from dataclasses import dataclass, field
from typing import TypedDict


class ChatMessage(TypedDict):
    """A single message in a conversation."""

    role: str
    content: str


@dataclass
class Session:
    """Per-session chat state."""

    messages: list[ChatMessage] = field(default_factory=list)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)


class SessionStore:
    """Thread-safe in-memory store keyed by session identifier."""

    def __init__(self, history_limit: int) -> None:
        self._sessions: dict[str, Session] = {}
        self._history_limit = history_limit

    def get_or_create(self, session_id: str) -> Session:
        """Return existing session or create a new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = Session()
        return self._sessions[session_id]

    def clear(self, session_id: str) -> None:
        """Remove all messages for a session."""
        session = self.get_or_create(session_id)
        session.messages.clear()
        session.cancel_event.set()

    def request_cancel(self, session_id: str) -> None:
        """Signal an in-flight stream to stop."""
        session = self._sessions.get(session_id)
        if session is not None:
            session.cancel_event.set()

    def reset_cancel(self, session_id: str) -> None:
        """Clear cancellation flag before starting a new stream."""
        session = self.get_or_create(session_id)
        session.cancel_event.clear()

    def append_message(self, session_id: str, message: ChatMessage) -> None:
        """Add a message and trim history to the configured limit."""
        session = self.get_or_create(session_id)
        session.messages.append(message)
        if len(session.messages) > self._history_limit:
            session.messages = session.messages[-self._history_limit :]

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        """Return a copy of the session's message history."""
        session = self.get_or_create(session_id)
        return list(session.messages)
