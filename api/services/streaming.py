"""Utilities for streaming chat completion responses as SSE payloads."""

from __future__ import annotations

import json
from typing import Iterable, Iterator, List

from api.models.chat import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkChoiceDelta,
    ChatCompletionResponse,
)


def iter_sse_from_response(response: ChatCompletionResponse) -> Iterator[str]:
    """Yield SSE payloads for the provided completion."""

    content = extract_content(response.choices[0].message.content)
    first_chunk = True
    for text_chunk in chunk_content(content):
        delta = ChatCompletionChunkChoiceDelta(
            role="assistant" if first_chunk else None,
            content=text_chunk,
        )
        first_chunk = False
        chunk = ChatCompletionChunk(
            id=response.id,
            object="chat.completion.chunk",
            created=response.created,
            model=response.model,
            choices=[
                ChatCompletionChunkChoice(index=0, delta=delta, finish_reason=None)
            ],
        )
        yield encode_sse_chunk(chunk)

    final_chunk = ChatCompletionChunk(
        id=response.id,
        object="chat.completion.chunk",
        created=response.created,
        model=response.model,
        choices=[
            ChatCompletionChunkChoice(
                index=0,
                delta=ChatCompletionChunkChoiceDelta(role=None, content=None),
                finish_reason=response.choices[0].finish_reason or "stop",
            )
        ],
    )
    yield encode_sse_chunk(final_chunk)
    yield "data: [DONE]\n\n"


def extract_content(content: object | None) -> str:
    if content is None:
        return ""
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


def chunk_content(content: str, size: int = 64) -> Iterable[str]:
    if not content:
        yield ""
        return
    for idx in range(0, len(content), size):
        yield content[idx : idx + size]


def encode_sse_chunk(chunk: ChatCompletionChunk) -> str:
    payload = json.dumps(chunk.model_dump(mode="json"))
    return f"data: {payload}\n\n"

