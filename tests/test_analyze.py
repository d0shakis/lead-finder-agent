import pytest

from leadfinder.llm import get_analyzer
from leadfinder.llm.base import LLMAnalyzer, parse_analysis
from leadfinder.llm.rules import RuleAnalyzer
from leadfinder.models import Business, WebsiteSignals

NO_SITE = Business(osm_id="n/1", name="Old School Plumbing", phone="123")
GREAT_SITE = Business(osm_id="n/2", name="Modern Pipes", website="https://m.gr", phone="1")
GREAT_SIGNALS = WebsiteSignals(
    reachable=True,
    https=True,
    mobile_friendly=True,
    has_contact_form=True,
    has_booking=True,
    has_chat_widget=True,
    has_analytics=True,
    has_h1=True,
    description="Plumbers",
    social_links=["https://facebook.com/m"],
    response_ms=300,
)


async def test_rules_rank_weak_presence_higher():
    rules = RuleAnalyzer()
    weak = await rules.analyze(NO_SITE, None)
    strong = await rules.analyze(GREAT_SITE, GREAT_SIGNALS)
    assert weak.score > strong.score
    assert "No website listed" in weak.problems
    assert weak.pitch.startswith("Hi Old School Plumbing")


async def test_rules_flag_outdated_site_without_analytics():
    stale = GREAT_SIGNALS.model_copy(update={"has_analytics": False, "copyright_year": 2015})
    a = await RuleAnalyzer().analyze(GREAT_SITE, stale)
    assert "Site looks outdated (© 2015)" in a.problems
    assert any("analytics" in p.lower() for p in a.problems)


async def test_rules_penalise_unreachable_businesses():
    ghost = await RuleAnalyzer().analyze(Business(osm_id="n/3", name="Ghost"), None)
    reachable = await RuleAnalyzer().analyze(NO_SITE, None)
    assert ghost.score < reachable.score


def test_parse_analysis_extracts_and_clamps():
    text = 'Sure! {"score": 140, "problems": ["no https"], "opportunities": [], "pitch": "Hi"} thanks'
    a = parse_analysis(text, "claude:x")
    assert a.score == 100 and a.problems == ["no https"] and a.provider == "claude:x"
    with pytest.raises(ValueError):
        parse_analysis("no json here", "x")


class FakeLLM(LLMAnalyzer):
    name = "fake"

    def __init__(self, reply):
        super().__init__("fake-1")
        self.reply = reply

    async def _complete(self, system, user):
        assert "Old School Plumbing" in user
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


async def test_llm_analyzer_success_and_fallback():
    ok = await FakeLLM('{"score": 77, "pitch": "Hello"}').analyze(NO_SITE, None)
    assert ok.score == 77 and ok.provider == "fake:fake-1"

    bad = await FakeLLM("I cannot answer").analyze(NO_SITE, None)
    assert bad.provider.startswith("rules (fallback")

    boom = await FakeLLM(RuntimeError("401")).analyze(NO_SITE, None)
    assert boom.provider == "rules (fallback: RuntimeError)"


def test_get_analyzer_auto_without_keys(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(get_analyzer("auto"), RuleAnalyzer)
    with pytest.raises(ValueError):
        get_analyzer("gemini")
