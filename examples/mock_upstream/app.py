from __future__ import annotations

from datetime import datetime
from typing import Dict

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Upstream")


class ChatRequest(BaseModel):
    model: str
    messages: list[dict]
    temperature: float | None = None


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "mock-upstream"}


@app.post("/v1/chat/completions")
async def chat_completions(payload: ChatRequest) -> Dict[str, object]:
    last_user = next((m["content"] for m in reversed(payload.messages) if m.get("role") == "user"), "")
    now = int(datetime.utcnow().timestamp())
    return {
        "id": "mock-cmpl",
        "object": "chat.completion",
        "created": now,
        "model": payload.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": f"Mock upstream response to: {last_user}"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
