"""Concrete LLM providers. SDKs are imported lazily so they stay optional."""

from __future__ import annotations

import os

import httpx

from leadfinder.llm.base import LLMAnalyzer


class ClaudeAnalyzer(LLMAnalyzer):
    name = "claude"

    def __init__(self, model: str | None = None):
        super().__init__(model or os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"))
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY

    async def _complete(self, system: str, user: str) -> str:
        msg = await self._client.messages.create(
            model=self.model,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")


class OpenAIAnalyzer(LLMAnalyzer):
    name = "openai"

    def __init__(self, model: str | None = None):
        super().__init__(model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI()  # reads OPENAI_API_KEY

    async def _complete(self, system: str, user: str) -> str:
        resp = await self._client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""


class OllamaAnalyzer(LLMAnalyzer):
    name = "ollama"

    def __init__(self, model: str | None = None):
        super().__init__(model or os.getenv("OLLAMA_MODEL", "llama3.1"))
        self._url = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/") + "/api/chat"

    async def _complete(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                self._url,
                json={
                    "model": self.model,
                    "format": "json",
                    "stream": False,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
