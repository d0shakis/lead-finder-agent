import httpx
import respx

from leadfinder.enrich import enrich_all, extract_signals, fetch_signals
from leadfinder.models import Business

GOOD_HTML = """<html><head><title>Pipe Pros</title>
<meta name="viewport" content="width=device-width">
<meta name="description" content="Plumbing in Thessaloniki"></head>
<body><form><input type="email" name="e"><textarea></textarea></form>
<a href="https://www.facebook.com/pipepros?ref=x">FB</a>
<a href="mailto:info@pipepros.gr">mail</a>
<script src="https://assets.calendly.com/widget.js"></script>
<p>We fix pipes fast.</p></body></html>"""

BAD_HTML = "<html><head><title>Old site</title></head><body>Call us. logo@2x.png</body></html>"


def test_extract_signals_good_site():
    s = extract_signals(GOOD_HTML, "https://pipepros.gr/")
    assert s.https and s.mobile_friendly and s.has_contact_form and s.has_booking
    assert s.social_links == ["https://www.facebook.com/pipepros"]
    assert s.emails == ["info@pipepros.gr"]
    assert s.title == "Pipe Pros"
    assert "We fix pipes fast." in s.text_excerpt
    assert "calendly" not in s.text_excerpt  # scripts stripped from text


def test_extract_signals_bad_site():
    s = extract_signals(BAD_HTML, "http://old.gr/")
    assert not (s.https or s.mobile_friendly or s.has_contact_form or s.has_booking)
    assert s.emails == []  # image filenames are not emails


OLD_WP_HTML = """<html><head><title>Old</title>
<link rel="stylesheet" href="/wp-content/themes/x/style.css">
<script>gtag('config', 'G-1');</script></head>
<body><h1>Hi</h1><a href="/contact-us">Contact</a><a href="https://other.com/contact">x</a>
<footer>&copy; 2009 - 2016 Old Plumbing</footer></body></html>"""

CONTACT_HTML = """<html><body><form><input type="text"><textarea></textarea></form>
<a href="mailto:office@old.gr">mail</a></body></html>"""


def test_extract_signals_cms_analytics_copyright_contact():
    s = extract_signals(OLD_WP_HTML, "https://old.gr/")
    assert s.cms == "WordPress"
    assert s.has_analytics and not s.has_ad_pixel
    assert s.copyright_year == 2016
    assert s.has_h1
    assert s.contact_page == "https://old.gr/contact-us"  # same-site link only


@respx.mock
async def test_fetch_signals_merges_contact_page():
    respx.get("https://old.gr/").mock(return_value=httpx.Response(200, text=OLD_WP_HTML))
    respx.get("https://old.gr/contact-us").mock(return_value=httpx.Response(200, text=CONTACT_HTML))
    async with httpx.AsyncClient() as client:
        s = await fetch_signals(client, "https://old.gr/")
    assert s.has_contact_form
    assert s.emails == ["office@old.gr"]


@respx.mock
async def test_fetch_signals_errors():
    respx.get("http://down.gr").mock(side_effect=httpx.ConnectError("nope"))
    respx.get("http://gone.gr").mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as client:
        down = await fetch_signals(client, "http://down.gr")
        gone = await fetch_signals(client, "http://gone.gr")
    assert not down.reachable and down.error == "ConnectError"
    assert not gone.reachable and gone.error == "HTTP 404"


@respx.mock
async def test_enrich_all_skips_businesses_without_website():
    respx.get("https://pipepros.gr").mock(return_value=httpx.Response(200, text=GOOD_HTML))
    businesses = [
        Business(osm_id="n/1", name="A", website="https://pipepros.gr"),
        Business(osm_id="n/2", name="B"),
    ]
    async with httpx.AsyncClient() as client:
        result = await enrich_all(client, businesses)
    assert result[0].reachable and result[1] is None
