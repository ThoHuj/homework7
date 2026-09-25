"""LiteLLM async streaming wrapper."""

import asyncio
import logging
from collections.abc import AsyncIterator

from litellm import acompletion

from chat_bot.sessions import ChatMessage

logger = logging.getLogger(__name__)


async def stream_completion(
    messages: list[ChatMessage],
    model: str,
    cancel_event: asyncio.Event,
) -> AsyncIterator[str]:
    """Stream content deltas from the LLM, stopping when cancel is requested."""
    response = await acompletion(model=model, messages=messages, stream=True)

    async for chunk in response:
        if cancel_event.is_set():
            break

        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
