"""Website scraper.

Crawls the paginated /communities directory to exhaustion AND scans the
homepage for community links that are absent from the directory (that is how
a homepage-only community gets caught). Extracts one normalized record per
detail page. Fails loudly if nothing parses; warns if the location count
moved more than 20% versus the previous run's snapshot.
"""
import html
import json
import os
import re
from datetime import datetime, timezone

import requests

from . import config

_SLUG_RE = re.compile(r'href="/communities/([a-z0-9\-]+)"')
_PAGER_RE = re.compile(r"Page\s+(\d+)\s*/\s*(\d+)")
_H1_RE = re.compile(r"<h1>(.*?)</h1>", re.S)
_ADDR_RE = re.compile(r"<dt>Address</dt>\s*<dd>(.*?)<br\s*/?>(.*?)</dd>", re.S)
_BADGE_RE = re.compile(r'<span class="badge">(.*?)</span>', re.S)
_ADMIN_RE = re.compile(r"<dt>Administrator</dt>\s*<dd>(.*?)</dd>", re.S)
_PHONE_RE = re.compile(r"<dt>Phone</dt>\s*<dd>(.*?)</dd>", re.S)
_CSZ_RE = re.compile(r"^(.*?),\s*([A-Z]{2})\s+(\d{5})(?:-\d{4})?$")


def _get(session, path):
    r = session.get(config.SITE_BASE.rstrip("/") + path, timeout=30)
    r.raise_for_status()
    return r.text


def _text(m, group=1):
    return html.unescape(m.group(group)).strip() if m else ""


def _parse_detail(slug, page):
    name = _text(_H1_RE.search(page))
    addr_m = _ADDR_RE.search(page)
    street, city, state, zip_code, raw_csz = "", "", "", "", ""
    if addr_m:
        street = html.unescape(addr_m.group(1)).strip()
        raw_csz = html.unescape(addr_m.group(2)).strip()
        csz = _CSZ_RE.match(raw_csz)
        if csz:
            city, state, zip_code = csz.group(1).strip(), csz.group(2), csz.group(3)
    offerings = [html.unescape(b).strip() for b in _BADGE_RE.findall(page)]
    return {
        "slug": slug,
        "url": f"{config.SITE_BASE.rstrip('/')}/communities/{slug}",
        "name": name,
        "address": street,
        "city": city,
        "state": state,
        "zip": zip_code,
        "raw_city_state_zip": raw_csz,
        "care_offerings": offerings,
        "administrator": _text(_ADMIN_RE.search(page)),
        "phone": _text(_PHONE_RE.search(page)),
    }


def scrape():
    """Returns {"locations": [...], "warnings": [...], "homepage_only": [...]}."""
    session = requests.Session()
    warnings = []

    # 1. Directory, all pages.
    directory_slugs = []
    first = _get(session, "/communities")
    pager = _PAGER_RE.search(first)
    total_pages = int(pager.group(2)) if pager else 1
    pages = [first] + [
        _get(session, f"/communities?page={p}") for p in range(2, total_pages + 1)
    ]
    for page in pages:
        for slug in _SLUG_RE.findall(page):
            if slug not in directory_slugs:
                directory_slugs.append(slug)

    # 2. Homepage scan for links missing from the directory.
    homepage = _get(session, "/")
    homepage_only = [
        s for s in _SLUG_RE.findall(homepage) if s not in directory_slugs
    ]
    all_slugs = directory_slugs + [s for s in homepage_only if s not in directory_slugs]

    # 3. Detail pages.
    locations = []
    for slug in all_slugs:
        page = _get(session, f"/communities/{slug}")
        loc = _parse_detail(slug, page)
        loc["homepage_only"] = slug in homepage_only
        if not loc["name"] or not loc["city"] or not loc["state"]:
            warnings.append(
                f"partial parse for '{slug}': name={loc['name']!r} "
                f"csz={loc['raw_city_state_zip']!r}"
            )
        locations.append(loc)

    if not locations:
        raise RuntimeError("Scraper parsed zero locations — aborting run.")

    # 4. Snapshot comparison (>20% swing is suspicious).
    os.makedirs(config.DATA_DIR, exist_ok=True)
    prev_count = None
    if os.path.exists(config.SNAPSHOT_PATH):
        try:
            with open(config.SNAPSHOT_PATH, encoding="utf-8") as f:
                prev_count = json.load(f).get("count")
        except (json.JSONDecodeError, OSError):
            warnings.append("previous scrape snapshot unreadable; skipping delta check")
    if prev_count:
        delta = abs(len(locations) - prev_count) / prev_count
        if delta > 0.20:
            warnings.append(
                f"location count changed {delta:.0%} vs previous run "
                f"({prev_count} -> {len(locations)}) — verify the site before approving"
            )
    with open(config.SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "count": len(locations),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "locations": locations,
            },
            f,
            indent=2,
        )

    return {"locations": locations, "warnings": warnings, "homepage_only": homepage_only}
