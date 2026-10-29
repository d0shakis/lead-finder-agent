from __future__ import annotations

from pydantic import BaseModel, Field


class Business(BaseModel):
    """A business discovered on OpenStreetMap."""

    osm_id: str
    name: str
    category: str = ""
    lat: float | None = None
    lon: float | None = None
    address: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    opening_hours: str = ""


class WebsiteSignals(BaseModel):
    """What we learned by fetching a business's homepage."""

    reachable: bool = False
    status_code: int | None = None
    final_url: str = ""
    https: bool = False
    response_ms: int | None = None
    mobile_friendly: bool = False
    has_contact_form: bool = False
    has_booking: bool = False
    has_chat_widget: bool = False
    has_analytics: bool = False
    has_ad_pixel: bool = False
    cms: str = ""
    copyright_year: int | None = None
    has_h1: bool = False
    contact_page: str = ""
    social_links: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    title: str = ""
    description: str = ""
    text_excerpt: str = ""
    error: str = ""


class LeadAnalysis(BaseModel):
    """The verdict on how good a lead a business is."""

    score: int = Field(ge=0, le=100)
    problems: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    pitch: str = ""
    provider: str = "rules"


class Lead(BaseModel):
    business: Business
    signals: WebsiteSignals | None = None
    analysis: LeadAnalysis | None = None

    def to_row(self) -> dict:
        """Flatten into a single dict for CSV / tables."""
        b, s, a = self.business, self.signals, self.analysis
        return {
            "score": a.score if a else None,
            "name": b.name,
            "category": b.category,
            "address": b.address,
            "phone": b.phone,
            "email": b.email or (s.emails[0] if s and s.emails else ""),
            "website": b.website,
            "https": s.https if s else None,
            "mobile_friendly": s.mobile_friendly if s else None,
            "contact_form": s.has_contact_form if s else None,
            "online_booking": s.has_booking if s else None,
            "analytics": s.has_analytics if s else None,
            "cms": s.cms if s else "",
            "copyright_year": s.copyright_year if s else None,
            "problems": "; ".join(a.problems) if a else "",
            "opportunities": "; ".join(a.opportunities) if a else "",
            "pitch": a.pitch if a else "",
            "provider": a.provider if a else "",
            "lat": b.lat,
            "lon": b.lon,
            "osm_id": b.osm_id,
        }
