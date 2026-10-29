"""Offline, deterministic lead scoring. Used when no LLM is configured, and as a fallback."""

from __future__ import annotations

import datetime as dt

from leadfinder.models import Business, LeadAnalysis, WebsiteSignals


class RuleAnalyzer:
    name = "rules"

    async def analyze(self, business: Business, signals: WebsiteSignals | None) -> LeadAnalysis:
        score = 30
        problems: list[str] = []
        opps: list[str] = []

        if not business.website:
            score += 35
            problems.append("No website listed")
            opps.append("Build a simple website with a contact form")
        elif signals is None or not signals.reachable:
            score += 30
            problems.append(f"Website unreachable ({signals.error if signals else 'not checked'})")
            opps.append("Fix or rebuild the broken website")
        else:
            if not signals.https:
                score += 10
                problems.append("No HTTPS")
            if not signals.mobile_friendly:
                score += 10
                problems.append("Not mobile-friendly")
                opps.append("Responsive redesign")
            if signals.response_ms and signals.response_ms > 3000:
                score += 5
                problems.append(f"Slow homepage ({signals.response_ms} ms)")
            if not signals.has_contact_form:
                score += 10
                problems.append("No contact form")
                opps.append("Lead capture form connected to a CRM")
            if not signals.has_booking:
                score += 10
                problems.append("No online booking")
                opps.append("Online booking + automated reminders")
            if not signals.has_chat_widget:
                score += 5
                opps.append("Chat / WhatsApp widget")
            if not signals.social_links:
                score += 5
                problems.append("No social media links")
            if not signals.has_analytics:
                score += 5
                problems.append("No analytics: can't measure marketing")
                opps.append("Analytics + lead tracking dashboard")
            stale_year = dt.date.today().year - 3
            if signals.copyright_year and signals.copyright_year <= stale_year:
                score += 5
                problems.append(f"Site looks outdated (© {signals.copyright_year})")
            if not signals.description or not signals.has_h1:
                score += 3
                problems.append("Weak SEO basics (missing meta description or H1)")

        if not business.phone and not business.email and not (signals and signals.emails):
            score -= 15
            problems.append("No contact details found (hard to reach)")

        score = max(0, min(100, score))
        main = opps[0].lower() if opps else "a quick digital check-up"
        pitch = f"Hi {business.name} team, I noticed a few quick wins for you, starting with {main}."
        return LeadAnalysis(score=score, problems=problems, opportunities=opps, pitch=pitch, provider="rules")
