import requests
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

API_PATH_HINTS = ("/api/", "/v1/", "/v2/", "/graphql", "/rest/")


def detect_type(url: str, headers: dict) -> dict:
    content_type = headers.get("Content-Type", "").lower()
    path = urlparse(url).path.lower()

    signals = []

    if "application/json" in content_type:
        signals.append(("content_type_json", "api", 0.8))
    elif "text/html" in content_type:
        signals.append(("content_type_html", "website", 0.7))

    if any(hint in path for hint in API_PATH_HINTS):
        signals.append(("path_hint", "api", 0.6))

    api_score = sum(w for _, kind, w in signals if kind == "api")
    site_score = sum(w for _, kind, w in signals if kind == "website")

    if api_score == 0 and site_score == 0:
        classification, confidence = "unknown", 0.0
    elif api_score >= site_score:
        classification = "api"
        confidence = min(api_score, 1.0)
    else:
        classification = "website"
        confidence = min(site_score, 1.0)

    return {
        "classification": classification,
        "confidence": confidence,
        "signals": signals,
    }


def try_find_sitemap(base_url: str, timeout: float = 5.0) -> dict:
    parsed = urlparse(base_url)
    sitemap_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/sitemap.xml")

    try:
        resp = requests.get(sitemap_url, timeout=timeout)
        if resp.status_code == 200 and "xml" in resp.headers.get("Content-Type", ""):
            return {"found": True, "sitemap_url": sitemap_url, "raw": resp.text}
        return {"found": False, "sitemap_url": sitemap_url}
    except requests.exceptions.RequestException:
        return {"found": False, "sitemap_url": sitemap_url, "error": "unreachable"}


def extract_paths_from_sitemap(sitemap_xml: str, max_paths: int = 20) -> list:
    """
    Parses <loc> entries out of a sitemap.xml and returns just the
    path portion (e.g. '/about', '/blog/post-1') so Locust can hit
    them relative to --host.
    """
    try:
        root = ET.fromstring(sitemap_xml)
    except ET.ParseError:
        return []

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = root.findall(".//sm:loc", ns) or root.findall(".//loc")

    paths = []
    for loc in locs[:max_paths]:
        url_text = (loc.text or "").strip()
        if url_text:
            paths.append(urlparse(url_text).path or "/")

    return paths