"""Chat completion service that delegates to the agent executor."""

from __future__ import annotations

from time import perf_counter
from typing import AsyncIterator

from fastapi import HTTPException, status

from agents.executor import agent_executor
from agents.executor import AgentExecutionError, AgentNotFoundError
from api.metrics import metrics
from api.models.chat import ChatCompletionRequest, ChatCompletionResponse
from api.services.streaming import iter_sse_from_response


from security import AuthContext


class ChatCompletionService:
    """Runs chat completions against registered agents and upstreams."""

    async def create_completion(
        self, request: ChatCompletionRequest, auth: AuthContext
    ) -> ChatCompletionResponse:
        response, latency = await self._execute(request, auth)
        metrics.record_completion(latency_ms=latency, streaming=False)
        return response

    async def stream_completion(
        self, request: ChatCompletionRequest, auth: AuthContext
    ) -> AsyncIterator[str]:
        start = perf_counter()
        async def _generator() -> AsyncIterator[str]:
            try:
                async for chunk in agent_executor.stream_completion(request, auth):
                    yield chunk
            except AgentNotFoundError as exc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
            except PermissionError as exc:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
            except AgentExecutionError as exc:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
            finally:
                latency_ms = (perf_counter() - start) * 1000
                metrics.record_completion(latency_ms=latency_ms, streaming=True)

        async for chunk in _generator():
            yield chunk

    async def _execute(
        self, request: ChatCompletionRequest, auth: AuthContext
    ) -> tuple[ChatCompletionResponse, float]:
        start = perf_counter()
        try:
            response = await agent_executor.create_completion(request, auth)
        except AgentNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
        except AgentExecutionError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
        latency_ms = (perf_counter() - start) * 1000
        return response, latency_ms


chat_service = ChatCompletionService()
