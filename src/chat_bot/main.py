"""FastAPI application: routes, SSE streaming, and static file serving."""

import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chat_bot.config import get_settings
from chat_bot.llm import stream_completion
from chat_bot.sessions import ChatMessage, SessionStore

logger = logging.getLogger(__name__)

SESSION_COOKIE = "session_id"
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"

session_store: SessionStore


class ChatRequest(BaseModel):
    """Incoming user message."""

    message: str


class HealthResponse(BaseModel):
    """Health check payload."""

    status: str


class StatusResponse(BaseModel):
    """Generic success response."""

    status: str


def _build_llm_messages(system_prompt: str, history: list[ChatMessage]) -> list[ChatMessage]:
    """Prepend system prompt to conversation history."""
    return [{"role": "system", "content": system_prompt}, *history]


def _ensure_session_cookie(response: Response, session_id: str | None) -> str:
    """Return existing session id or create one and set the cookie."""
    if session_id:
        return session_id
    new_session_id = str(uuid.uuid4())
    response.set_cookie(
        key=SESSION_COOKIE,
        value=new_session_id,
        httponly=True,
        samesite="lax",
    )
    return new_session_id


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialize shared resources on startup."""
    global session_store
    settings = get_settings()
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    session_store = SessionStore(history_limit=settings.history_limit)
    yield


app = FastAPI(lifespan=lifespan)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok")


@app.get("/")
async def index(
    response: Response,
    session_id: str | None = Cookie(default=None),
) -> FileResponse:
    """Serve the chat UI and ensure a session cookie exists."""
    _ensure_session_cookie(response, session_id)
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_path)


@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    response: Response,
    session_id: str | None = Cookie(default=None),
) -> StreamingResponse:
    """Stream an assistant reply via Server-Sent Events."""
    session_id = _ensure_session_cookie(response, session_id)
    settings = get_settings()

    user_message = request.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if not settings.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")

    session_store.reset_cancel(session_id)
    session_store.append_message(session_id, {"role": "user", "content": user_message})

    history = session_store.get_messages(session_id)
    llm_messages = _build_llm_messages(settings.system_prompt, history)
    cancel_event = session_store.get_or_create(session_id).cancel_event

    async def event_stream() -> AsyncIterator[str]:
        assistant_content = ""
        try:
            async for token in stream_completion(
                messages=llm_messages,
                model=settings.model,
                cancel_event=cancel_event,
            ):
                assistant_content += token
                yield f"data: {token}\n\n"
        except Exception:
            logger.exception("LLM streaming failed for session %s", session_id)
            error_message = "Sorry, something went wrong. Please try again."
            assistant_content = error_message
            yield f"data: [ERROR] {error_message}\n\n"
        finally:
            if assistant_content:
                session_store.append_message(
                    session_id,
                    {"role": "assistant", "content": assistant_content},
                )
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/chat/stop", response_model=StatusResponse)
async def stop_chat(
    response: Response,
    session_id: str | None = Cookie(default=None),
) -> StatusResponse:
    """Abort the current stream for this session."""
    session_id = _ensure_session_cookie(response, session_id)
    session_store.request_cancel(session_id)
    return StatusResponse(status="ok")


@app.post("/api/chat/new", response_model=StatusResponse)
async def new_chat(
    response: Response,
    session_id: str | None = Cookie(default=None),
) -> StatusResponse:
    """Clear session history and start a fresh conversation."""
    session_id = _ensure_session_cookie(response, session_id)
    session_store.clear(session_id)
    session_store.reset_cancel(session_id)
    return StatusResponse(status="ok")
