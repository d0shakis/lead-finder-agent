"""Shared analyzer interface and prompt for all LLM providers."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

from leadfinder.llm.rules import RuleAnalyzer
from leadfinder.models import Business, LeadAnalysis, WebsiteSignals

SYSTEM_PROMPT = """You are a B2B sales analyst for an agency that sells CRM setup, \
marketing automation, online booking and website improvements to small local businesses.

Given facts about one business and an audit of its website, judge how likely it is to \
benefit from (and buy) these services. Weak digital presence = higher score, but a business \
that is clearly closed, a big chain, or a government office scores low.

Respond with ONLY a JSON object, no prose, matching:
{"score": <int 0-100>, "problems": [<short strings>], "opportunities": [<short strings>], \
"pitch": "<one or two sentence personalised opening line for a cold email>"}"""


def build_user_prompt(business: Business, signals: WebsiteSignals | None) -> str:
    facts = business.model_dump(exclude={"osm_id", "lat", "lon"})
    audit = signals.model_dump() if signals else {"note": "Business has no website listed."}
    return (
        "BUSINESS:\n"
        + json.dumps(facts, ensure_ascii=False, indent=1)
        + "\n\nWEBSITE AUDIT:\n"
        + json.dumps(audit, ensure_ascii=False, indent=1)
    )


def parse_analysis(text: str, provider: str) -> LeadAnalysis:
    """Pull the first JSON object out of model output and validate it."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON object in model output")
    data = json.loads(match.group(0))
    data["score"] = max(0, min(100, int(data.get("score", 0))))
    data["provider"] = provider
    return LeadAnalysis.model_validate(data)


class Analyzer(ABC):
    name = "base"

    @abstractmethod
    async def analyze(self, business: Business, signals: WebsiteSignals | None) -> LeadAnalysis: ...


class LLMAnalyzer(Analyzer):
    """Base for LLM providers: calls the model, falls back to rules on bad output or errors."""

    def __init__(self, model: str):
        self.model = model
        self._fallback = RuleAnalyzer()

    @abstractmethod
    async def _complete(self, system: str, user: str) -> str: ...

    async def analyze(self, business: Business, signals: WebsiteSignals | None) -> LeadAnalysis:
        try:
            text = await self._complete(SYSTEM_PROMPT, build_user_prompt(business, signals))
            return parse_analysis(text, f"{self.name}:{self.model}")
        except Exception as e:  # bad JSON, validation, network or auth errors
            result = await self._fallback.analyze(business, signals)
            result.provider = f"rules (fallback: {type(e).__name__})"
            return result
