"""Streamlit UI for the Lead Finder Agent.  Run:  streamlit run app.py"""

from __future__ import annotations

import asyncio
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from leadfinder.agent import find_leads
from leadfinder.demo import DEMO_CITY, DEMO_TERM, load_demo
from leadfinder.llm import PROVIDERS
from leadfinder.sources.osm import GeocodeError

load_dotenv()
st.set_page_config(page_title="Lead Finder Agent", page_icon="🎯", layout="wide")


def show_demo() -> None:
    st.session_state["result"] = (DEMO_TERM, DEMO_CITY, load_demo())
    st.session_state["is_demo"] = True


# Hosted demos (e.g. Streamlit Cloud) can start with sample data: set LEADFINDER_DEMO=1
if os.getenv("LEADFINDER_DEMO") == "1" and "result" not in st.session_state:
    show_demo()

st.title("🎯 Lead Finder Agent")
st.caption(
    "Finds local businesses on OpenStreetMap, audits their websites, and uses AI to score "
    "how likely each one is to need CRM & automation services."
)

with st.sidebar:
    st.header("Settings")
    provider = st.selectbox("AI provider", PROVIDERS, help="'auto' uses Claude or OpenAI if a key is set, else rules.")
    if provider in ("claude", "auto") and not os.getenv("ANTHROPIC_API_KEY"):
        key = st.text_input("Anthropic API key (optional)", type="password")
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        key = st.text_input("OpenAI API key", type="password")
        if key:
            os.environ["OPENAI_API_KEY"] = key
    model = st.text_input("Model override (optional)") or None
    limit = st.slider("Max businesses", 5, 100, 25)
    skip_websites = st.checkbox("Skip website audit (faster)")
    st.divider()
    st.button("Load demo data", on_click=show_demo, help="Sample results bundled with the app, no network needed.")
    st.caption("Data © OpenStreetMap contributors (ODbL)")

with st.form("search"):
    c1, c2, c3 = st.columns([2, 2, 1])
    term = c1.text_input("Business type", "plumber", help="e.g. plumber, dentist, gym, hairdresser")
    city = c2.text_input("City", "Thessaloniki")
    c3.write("")
    submitted = c3.form_submit_button("Find leads", type="primary", width="stretch")

if submitted:
    bar = st.progress(0.0, text="Starting...")
    try:
        result = asyncio.run(
            find_leads(
                term,
                city,
                limit,
                provider,
                model,
                skip_websites,
                progress=lambda msg, frac: bar.progress(min(frac, 1.0), text=msg),
            )
        )
    except GeocodeError as e:
        st.error(str(e))
        st.stop()
    except Exception as e:  # network errors from public OSM servers, bad provider, etc.
        st.error(f"Search failed: {e}")
        st.button("Show demo results instead", on_click=show_demo)
        st.stop()
    bar.empty()
    st.session_state["result"] = (term, city, result)
    st.session_state["is_demo"] = False

if "result" in st.session_state:
    term, city, result = st.session_state["result"]
    if st.session_state.get("is_demo"):
        st.info(f"Showing bundled demo data ({DEMO_TERM} in {DEMO_CITY}). Run a search for live results.")
    if not result.leads:
        st.warning("No businesses found. Try a different business type or a bigger city.")
        st.stop()

    df = pd.DataFrame([l.to_row() for l in result.leads])
    if df["provider"].str.contains("fallback").any():
        st.warning("The AI provider failed for some leads, so rule-based scoring was used. Check your API key / model.")
    hot = (df["score"] >= 70).sum()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Businesses found", len(df))
    m2.metric("Hot leads (≥70)", int(hot))
    m3.metric("No website", int((df["website"] == "").sum()))
    m4.metric("Average score", f"{df['score'].mean():.0f}")

    st.subheader(f"Leads: {term} in {result.area_name}")
    st.dataframe(
        df[["score", "name", "website", "phone", "email", "problems", "pitch"]],
        column_config={
            "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
            "website": st.column_config.LinkColumn("Website"),
        },
        hide_index=True,
        width="stretch",
    )

    tab_map, tab_detail = st.tabs(["🗺️ Map", "🔍 Lead details"])
    with tab_map:
        st.map(df.dropna(subset=["lat", "lon"]), latitude="lat", longitude="lon")
    with tab_detail:
        for lead in result.leads[:20]:
            a = lead.analysis
            with st.expander(f"{a.score} · {lead.business.name}"):
                st.markdown(f"**Pitch:** {a.pitch}")
                d1, d2 = st.columns(2)
                d1.markdown(
                    "**Problems**\n" + "\n".join(f"- {p}" for p in a.problems) if a.problems else "No problems found"
                )
                d2.markdown(
                    "**Opportunities**\n" + "\n".join(f"- {o}" for o in a.opportunities) if a.opportunities else ""
                )
                s = lead.signals
                if s and s.reachable:
                    checks = {
                        "HTTPS": s.https,
                        "Mobile": s.mobile_friendly,
                        "Contact form": s.has_contact_form,
                        "Booking": s.has_booking,
                        "Chat": s.has_chat_widget,
                        "Analytics": s.has_analytics,
                    }
                    st.markdown(" · ".join(f"{'✅' if ok else '❌'} {name}" for name, ok in checks.items()))
                    extra = [
                        x
                        for x in (
                            s.cms and f"CMS: {s.cms}",
                            s.copyright_year and f"© {s.copyright_year}",
                            s.response_ms and f"{s.response_ms} ms",
                        )
                        if x
                    ]
                    if extra:
                        st.caption(" · ".join(extra))
                contact = " · ".join(x for x in (lead.business.phone, lead.business.email, lead.business.address) if x)
                if contact:
                    st.caption(f"📇 {contact}")
                st.caption(
                    f"Scored by {a.provider} · [OSM {lead.business.osm_id}](https://www.openstreetmap.org/{lead.business.osm_id})"
                )

    st.download_button(
        "⬇️ Download CSV",
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"leads_{term}_{city}.csv".replace(" ", "_"),
        mime="text/csv",
    )
