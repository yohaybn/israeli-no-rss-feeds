"""Replace scrape-batch item dates with the real publish time read from each article page.

html2rss often cannot find a date in a listing page and stamps every such item with the
time of the scan, so many items share one pubDate that is not their publish time. For the
items that look affected (their date is shared by 2 or more items, or the date is missing),
the article page is fetched once and its own published time is used. Stdlib only.
"""
import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from feedlib import _iso_to_dt, _rfc822

CLUSTER_MIN = 2          # identical dates on 2+ items almost always mean a scan time, not publish times
MAX_FETCH_PER_FEED = 30
_META = re.compile(r'<meta\b[^>]*>', re.I)
_ATTR = re.compile(r'([a-zA-Z_:-]+)\s*=\s*("([^"]*)"|\'([^\']*)\')')
_JSONLD = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.I | re.S)
_DATE_KEYS = ('article:published_time', 'og:article:published_time', 'datepublished',
              'article:publishdate', 'publishdate', 'pubdate', 'date')


def _attrs(tag):
    return {m.group(1).lower(): html.unescape(m.group(3) if m.group(3) is not None else m.group(4))
            for m in _ATTR.finditer(tag)}


def _walk(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == 'datePublished' and isinstance(value, str):
                yield value
            else:
                yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def parse_article_date(page, now=None):
    """The article's own publish time (aware, UTC) or None. Never returns a future time."""
    now = now or datetime.now(timezone.utc)
    if isinstance(page, bytes):
        page = page.decode('utf-8', 'ignore')
    candidates = []
    for tag in _META.findall(page):
        a = _attrs(tag)
        name = (a.get('property') or a.get('name') or a.get('itemprop') or '').lower()
        if name in _DATE_KEYS and a.get('content'):
            candidates.append(a['content'])
    for block in _JSONLD.findall(page):
        try:
            candidates.extend(_walk(json.loads(html.unescape(block).strip())))
        except ValueError:
            continue
    for text in candidates:
        dt = _iso_to_dt(text)
        if dt is not None and dt <= now + timedelta(minutes=10) and dt.year >= 2000:
            return dt.astimezone(timezone.utc)
    return None


def suspicious_urls(root):
    """Links of items whose date is missing or shared by 2 or more items."""
    items = root.findall('./channel/item')
    counts = {}
    for item in items:
        text = (item.findtext('pubDate') or '').strip()
        counts[text] = counts.get(text, 0) + 1
    return [item for item in items
            if not (item.findtext('pubDate') or '').strip()
            or counts[(item.findtext('pubDate') or '').strip()] >= CLUSTER_MIN]


def correct_batch_dates(xml_bytes, fetch, max_fetch=MAX_FETCH_PER_FEED, now=None):
    """Return (new_xml_bytes, number_of_dates_corrected). `fetch(url)` returns page text or None."""
    root = ET.fromstring(xml_bytes)
    fixed = fetched = 0
    for item in suspicious_urls(root):
        if fetched >= max_fetch:
            break
        link = (item.findtext('link') or '').strip()
        if not link:
            continue
        fetched += 1
        try:
            page = fetch(link)
        except Exception:
            page = None
        dt = parse_article_date(page, now) if page else None
        if dt is None:
            continue
        pub = item.find('pubDate')
        if pub is None:
            pub = ET.SubElement(item, 'pubDate')
        new = _rfc822(dt)
        if pub.text != new:
            pub.text = new
            fixed += 1
    if not fixed:
        return xml_bytes, 0
    return ET.tostring(root, encoding='UTF-8', xml_declaration=True), fixed
