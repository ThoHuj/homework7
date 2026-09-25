# chat-bot

A minimal streaming chat web app. Users ask questions in a terminal-styled browser UI; the server calls an LLM via LiteLLM and streams replies back. Conversation history is kept in memory per session.

## Stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.12+, FastAPI |
| LLM | LiteLLM (OpenAI default, swappable) |
| Frontend | Single HTML page, vanilla JS, CSS |
| Default model | `gpt-4o-mini` |
| Port | `8000` |

## Architecture

```
Browser (static/) ──POST /api/chat (SSE)──▶ FastAPI (src/chat_bot/)
                                                │
                                                ▼
                                          LiteLLM ──▶ OpenAI / Anthropic / …
```

- **Multi-turn chat**: server stores message history in memory, keyed by session cookie.
- **Streaming**: responses use Server-Sent Events; the UI appends tokens as they arrive.
- **History trim**: keep the last 20 messages per session (configurable).
- **Health**: `GET /health` returns `{"status": "ok"}`.

## Bot persona

The default system prompt defines an **overly enthusiastic cheerleader** assistant: upbeat, encouraging, exclamation marks welcome, celebrates the user's questions, still accurate and helpful. Override via `SYSTEM_PROMPT` env var.

## UI

Terminal/hacker aesthetic (monospace font, dark background, green/amber accents).

Features:
- Message input + send
- Streaming assistant replies with **markdown rendering** (code blocks, bold, lists)
- **New chat** — clears session history
- **Stop** — aborts in-flight streaming
- **Copy** — copy assistant reply to clipboard

Not in v1: model name display, mobile polish, auth, persistent storage.

## Project layout

```
.
├── AGENTS.md
├── src/
│   └── chat_bot/
│       ├── __init__.py
│       ├── main.py          # FastAPI app, routes, lifespan
│       ├── config.py        # env-based settings
│       ├── sessions.py      # in-memory session store
│       └── llm.py           # LiteLLM streaming wrapper
├── static/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── k8s/
│   ├── deployment.yaml
│   └── service.yaml
├── .env.example
└── docs/
```

Keep the app small. Prefer extending existing modules over new abstractions.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | yes* | — | API key for the default OpenAI model |
| `MODEL` | no | `gpt-4o-mini` | LiteLLM model string |
| `SYSTEM_PROMPT` | no | (cheerleader persona) | Override system instructions |
| `PORT` | no | `8000` | HTTP listen port |
| `HISTORY_LIMIT` | no | `20` | Max messages kept per session |

\*When using other providers, set the key LiteLLM expects (e.g. `ANTHROPIC_API_KEY`) and point `MODEL` accordingly.

## API

### `GET /health`

Returns `200` with `{"status": "ok"}`.

### `POST /api/chat`

Request body:

```json
{ "message": "user text" }
```

Response: `text/event-stream` — SSE chunks with assistant tokens, ending with a `[DONE]` event.

### `POST /api/chat/stop`

Aborts the current stream for the session.

### `POST /api/chat/new`

Clears session history, starts a fresh conversation.

## Conventions

- Type-annotate Python; use Pydantic models for request/response schemas.
- No database, no auth, no test suite in v1.
- Static assets served by FastAPI from `static/`.
- Session ID via HTTP-only cookie; generate on first visit.
- Handle LLM errors gracefully — show a user-friendly message in the UI, log details server-side.
- Do not commit secrets; use `.env` locally (gitignored).

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
uvicorn chat_bot.main:app --app-dir src --reload --port 8000
```

Open http://localhost:8000

## Docker

Build and run with plain Docker:

```bash
docker build -t chat-bot .
docker run --rm -p 8000:8000 --env-file .env chat-bot
```

Or with Docker Compose:

```bash
docker compose up --build
docker compose down
```

Use `docker compose` (with a space), not `docker-compose`.

## Kubernetes

Enable Kubernetes in Docker Desktop (Settings → Kubernetes → Enable), then:

```bash
docker build -t chat-bot .
kubectl create secret generic chat-bot-secrets --from-env-file=.env
kubectl apply -f k8s/
kubectl get pods,svc
```

Open http://localhost:30080 (NodePort). Tear down:

```bash
kubectl delete -f k8s/
kubectl delete secret chat-bot-secrets
```

## Out of scope (v1)

- User authentication
- Database / persistent chat history
- Automated tests
- Mobile-specific UI
