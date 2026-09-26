# chat-bot

A minimal streaming chat web app with a terminal-style UI. Ask questions in the browser; the server calls an LLM via [LiteLLM](https://github.com/BerriAI/litellm) and streams replies back. Conversation history is kept in memory per session.

## Features

- Multi-turn chat with streaming responses (SSE)
- Markdown rendering in assistant messages
- New chat, stop generation, and copy reply
- Overly enthusiastic cheerleader persona (override via env)
- Runs locally, in Docker, Compose, or Kubernetes

## Quick start

```bash
cp .env.example .env   # add your OPENAI_API_KEY
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn chat_bot.main:app --app-dir src --reload --port 8000
```

Open http://localhost:8000

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | yes* | — | API key for the default OpenAI model |
| `MODEL` | no | `gpt-4o-mini` | LiteLLM model string |
| `SYSTEM_PROMPT` | no | cheerleader persona | Override system instructions |
| `PORT` | no | `8000` | HTTP listen port |
| `HISTORY_LIMIT` | no | `20` | Max messages kept per session |

\*For other providers, set the key LiteLLM expects (e.g. `ANTHROPIC_API_KEY`) and point `MODEL` accordingly.

## Docker

```bash
docker build -t chat-bot .
docker run --rm -p 8000:8000 --env-file .env chat-bot
```

## Docker Compose

```bash
docker compose up --build
docker compose down
```

## Kubernetes (Docker Desktop)

```bash
docker build -t chat-bot .
kubectl create secret generic chat-bot-secrets --from-env-file=.env
kubectl apply -f k8s/
```

Open http://localhost:8000, then tear down:

```bash
kubectl delete -f k8s/
kubectl delete secret chat-bot-secrets
```

## Project structure

```
src/chat_bot/   FastAPI backend
static/         Terminal-style web UI
k8s/            Kubernetes manifests
```

See [AGENTS.md](AGENTS.md) for architecture details and agent conventions.
