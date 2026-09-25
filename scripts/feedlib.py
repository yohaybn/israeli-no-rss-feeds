"""Shared helpers: strip republication content from RSS 2.0 feeds and validate structure.

Policy: generated feeds carry title + link only (plus guid/pubDate). Article
bodies (<description>, <content:encoded>) are removed so the feeds never
republish site content.
"""
import re
import xml.etree.ElementTree as ET

CONTENT_NS = 'http://purl.org/rss/1.0/modules/content/'
ET.register_namespace('content', CONTENT_NS)
ET.register_namespace('atom', 'http://www.w3.org/2005/Atom')
ET.register_namespace('dc', 'http://purl.org/dc/elements/1.1/')

STRIP_LOCALNAMES = {'description', 'encoded', 'summary'}

SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')


def strip_item_content(xml_bytes):
    """Remove <description> / <content:encoded> from every item.

    Returns (clean_xml_bytes, item_count). Raises on unparseable input.
    """
    root = ET.fromstring(xml_bytes)
    items = list(root.iter('item'))
    for item in items:
        for child in list(item):
            local = child.tag.rsplit('}', 1)[-1]
            if local in STRIP_LOCALNAMES:
                item.remove(child)
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
