"""Shared helpers: strip republication content from RSS 2.0 feeds and validate structure.

Policy: generated feeds carry title + link only (plus guid/pubDate). Article
bodies (<description>, <content:encoded>) are removed so the feeds never
republish site content.
"""
import re
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

CONTENT_NS = 'http://purl.org/rss/1.0/modules/content/'
ET.register_namespace('content', CONTENT_NS)
ET.register_namespace('atom', 'http://www.w3.org/2005/Atom')
ET.register_namespace('dc', 'http://purl.org/dc/elements/1.1/')

STRIP_LOCALNAMES = {'description', 'encoded', 'summary'}

DC_NS = 'http://purl.org/dc/elements/1.1/'
ATOM_NS = 'http://www.w3.org/2005/Atom'

SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _rfc822(dt):
    from email.utils import format_datetime
    return format_datetime(dt, usegmt=True)


def _iso_to_rfc822(text):
    """Best-effort ISO-8601 (dc:date) to RFC-822 (pubDate); None on failure."""
    try:
        dt = datetime.fromisoformat(text.strip().replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return _rfc822(dt.astimezone(timezone.utc))


def strip_item_content(xml_bytes, feed_url=None, now=None):
    """Remove <description> / <content:encoded> from every item and normalize
    the channel for strict readers:

    - channel keeps exactly one pubDate (dc:date is folded in or dropped)
    - every channel element sits before the first <item> (html2rss appends
      dc:date after the items, which strict parsers reject as misplaced)
    - an <atom:link rel="self"> is added when feed_url is given
    - items without any date get pubDate = generation time

    Returns (clean_xml_bytes, item_count). Raises on unparseable input.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    now_rfc822 = _rfc822(now)
    root = ET.fromstring(xml_bytes)
    channel = root.find('channel')
    items = list(root.iter('item'))
    for item in items:
        for child in list(item):
            if _local(child.tag) in STRIP_LOCALNAMES:
                item.remove(child)
        has_pubdate = item.find('pubDate') is not None
        dc = item.find(f'{{{DC_NS}}}date')
        if dc is not None:
            if not has_pubdate:
                converted = _iso_to_rfc822(dc.text or '')
                if converted:
                    pub = ET.SubElement(item, 'pubDate')
                    pub.text = converted
                    has_pubdate = True
            item.remove(dc)
        if not has_pubdate:
            pub = ET.SubElement(item, 'pubDate')
            pub.text = now_rfc822
    if channel is not None:
        for dc in channel.findall(f'{{{DC_NS}}}date'):
            if channel.find('pubDate') is None:
                converted = _iso_to_rfc822(dc.text or '')
                if converted:
                    pub = ET.Element('pubDate')
                    pub.text = converted
                    channel.insert(list(channel).index(dc), pub)
            channel.remove(dc)
        # move any channel metadata that html2rss put after the items
        children = list(channel)
        first_item_idx = next((i for i, c in enumerate(children) if c.tag == 'item'), len(children))
        tail_meta = [c for c in children[first_item_idx:] if c.tag != 'item']
        for c in tail_meta:
            channel.remove(c)
        for offset, c in enumerate(tail_meta):
            channel.insert(next((i for i, x in enumerate(list(channel)) if x.tag == 'item'), len(list(channel))) , c)
        if feed_url and not any(l.get('rel') == 'self' for l in channel.findall(f'{{{ATOM_NS}}}link')):
            link = ET.Element(f'{{{ATOM_NS}}}link')
            link.set('href', feed_url)
            link.set('rel', 'self')
            link.set('type', 'application/rss+xml')
            anchor = channel.find('link')
            channel.insert(list(channel).index(anchor) + 1 if anchor is not None else 0, link)
    return ET.tostring(root, encoding='UTF-8', xml_declaration=True), len(items)


def validate_feed_bytes(xml_bytes):
    """Return a list of problems; empty list means a valid title+link RSS feed."""
    problems = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        return [f'XML parse error: {e}']
    if root.tag != 'rss':
        return [f'root element is <{root.tag}>, expected <rss>']
    channel = root.find('channel')
    if channel is None:
        return ['no <channel> element']
    if not (channel.findtext('title') or '').strip():
        problems.append('channel missing <title>')
    if not (channel.findtext('link') or '').strip():
        problems.append('channel missing <link>')
    items = channel.findall('item')
    if not items:
        problems.append('no <item> elements')
    for i, item in enumerate(items):
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        if not title:
            problems.append(f'item {i}: missing title')
        if not link:
            problems.append(f'item {i}: missing link')
        elif not re.match(r'https?://', link):
            problems.append(f'item {i}: link is not http(s): {link[:60]!r}')
        for child in list(item):
            local = child.tag.rsplit('}', 1)[-1]
            if local in STRIP_LOCALNAMES:
                problems.append(f'item {i}: still contains <{local}> (title+link policy)')
    return problems
