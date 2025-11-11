from __future__ import annotations

from api.models.chat import ChatCompletionChoice, ChatCompletionResponse, ChatMessage, Usage
from api.services.streaming import chunk_content, extract_content, iter_sse_from_response


def _build_response(text: str) -> ChatCompletionResponse:
    message = ChatMessage(role="assistant", content=text)
    choice = ChatCompletionChoice(index=0, message=message, finish_reason="stop")
    return ChatCompletionResponse(
        id="cmpl_test",
        object="chat.completion",
        created=123,
        model="demo",
        choices=[choice],
        usage=Usage(prompt_tokens=1, completion_tokens=len(text), total_tokens=len(text) + 1),
    )


def test_extract_content_handles_list_payload() -> None:
    content = [{"text": "Hello"}, {"text": "World"}]
    assert extract_content(content) == "HelloWorld"


def test_chunk_content_splits_text() -> None:
    chunks = list(chunk_content("abcdefgh", size=3))
    assert chunks == ["abc", "def", "gh"]


def test_iter_sse_from_response_yields_done_marker() -> None:
    response = _build_response("hello world")
    payloads = list(iter_sse_from_response(response))
    assert payloads[-1] == "data: [DONE]\\n\\n"
    assert payloads[0].startswith("data: ")
