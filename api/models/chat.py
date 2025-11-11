"""OpenAI-compatible chat completion request/response models."""

from __future__ import annotations

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


Role = Literal["system", "user", "assistant", "tool"]


class ToolCallFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"]
    function: ToolCallFunction


class ChatMessage(BaseModel):
    role: Role
    content: Optional[Union[str, List[dict]]] = None
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="Model name or agent identifier")
    messages: List[ChatMessage]
    temperature: float = 1.0
    max_tokens: Optional[int] = None
    stream: bool = False
    n: int = 1
    user: Optional[str] = None


FinishReason = Literal["stop", "length", "tool_calls", "content_filter"]


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: FinishReason


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"]
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage


class ChatCompletionChunkChoiceDelta(BaseModel):
    role: Optional[Role] = None
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class ChatCompletionChunkChoice(BaseModel):
    index: int
    delta: ChatCompletionChunkChoiceDelta
    finish_reason: Optional[FinishReason] = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"]
    created: int
    model: str
    choices: List[ChatCompletionChunkChoice]
