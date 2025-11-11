"""Chat completion route exposing OpenAI-compatible API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.auth import enforce_api_key
from api.models.chat import ChatCompletionRequest, ChatCompletionResponse
from api.services.chat import chat_service
from security import AuthContext


router = APIRouter(prefix="/v1", tags=["chat"])


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(
    request: ChatCompletionRequest,
    auth: AuthContext = Depends(enforce_api_key),
):
    """Handle both streaming and non-streaming chat completions."""

    if request.stream:
        generator = chat_service.stream_completion(request, auth=auth)
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )
    return await chat_service.create_completion(request, auth=auth)
