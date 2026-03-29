import asyncio

import httpx

from app.config import Settings
from app.gemini_service import GeminiChatService


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.is_error = False

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    async def post(self, url, *, headers, json):
        self.calls.append({"url": url, "headers": headers, "json": json})
        if not self.payloads:
            raise httpx.ConnectError("retry unavailable")
        return _FakeResponse(self.payloads.pop(0))

    async def aclose(self):
        return None


def _build_service(payloads):
    settings = Settings(
        GEMINI_API_KEY="test-key",
        GEMINI_MAX_OUTPUT_TOKENS=100,
    )
    service = GeminiChatService(settings)
    service.client = _FakeClient(payloads)
    return service


def test_generate_reply_retries_when_gemini_truncates_response():
    first_payload = {
        "candidates": [
            {
                "finishReason": "MAX_TOKENS",
                "content": {"parts": [{"text": "reponse tronquee"}]},
            }
        ]
    }
    second_payload = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": "reponse complete"}]},
            }
        ]
    }
    service = _build_service([first_payload, second_payload])

    result = asyncio.run(
        service.generate_reply(
            system_prompt="system",
            conversation_messages=[{"role": "user", "content": "question"}],
        )
    )

    assert result == "reponse complete"
    assert len(service.client.calls) == 2
    assert service.client.calls[0]["json"]["generationConfig"]["maxOutputTokens"] == 100
    assert service.client.calls[1]["json"]["generationConfig"]["maxOutputTokens"] == 1600


def test_generate_reply_returns_first_response_when_retry_is_unavailable():
    truncated_payload = {
        "candidates": [
            {
                "finishReason": "MAX_TOKENS",
                "content": {"parts": [{"text": "reponse partielle"}]},
            }
        ]
    }
    service = _build_service([truncated_payload])

    result = asyncio.run(
        service.generate_reply(
            system_prompt="system",
            conversation_messages=[{"role": "user", "content": "question"}],
        )
    )

    assert result == "reponse partielle"
