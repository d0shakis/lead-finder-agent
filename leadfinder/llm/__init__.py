"""Analyzer factory."""

from __future__ import annotations

import os

from leadfinder.llm.rules import RuleAnalyzer

PROVIDERS = ("auto", "rules", "claude", "openai", "ollama")


def get_analyzer(provider: str = "auto", model: str | None = None):
    """Return an analyzer. 'auto' picks Claude, then OpenAI if their keys are set, else rules."""
    provider = provider.lower()
    if provider == "auto":
        if os.getenv("ANTHROPIC_API_KEY"):
            provider = "claude"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        else:
            provider = "rules"

    if provider == "rules":
        return RuleAnalyzer()
    if provider == "claude":
        from leadfinder.llm.providers import ClaudeAnalyzer

        return ClaudeAnalyzer(model)
    if provider == "openai":
        from leadfinder.llm.providers import OpenAIAnalyzer

        return OpenAIAnalyzer(model)
    if provider == "ollama":
        from leadfinder.llm.providers import OllamaAnalyzer

        return OllamaAnalyzer(model)
    raise ValueError(f"Unknown provider {provider!r}. Choose from: {', '.join(PROVIDERS)}")
