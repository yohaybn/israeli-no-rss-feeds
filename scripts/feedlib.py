"""Shared helpers: normalize scraped feeds into clean RSS 2.0 and validate structure.

Policy: generated feeds carry title + link + a short plain-text teaser (capped)
+ an image enclosure when the source listing exposes one. Full article bodies
(<content:encoded>, long HTML descriptions) are never republished: descriptions
are converted to plain text and truncated to DESCRIPTION_MAX chars.
"""
import html
import json
import re
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

CONTENT_NS = 'http://purl.org/rss/1.0/modules/content/'
ET.register_namespace('content', CONTENT_NS)
ET.register_namespace('atom', 'http://www.w3.org/2005/Atom')
ET.register_namespace('dc', 'http://purl.org/dc/elements/1.1/')

DC_NS = 'http://purl.org/dc/elements/1.1/'
ATOM_NS = 'http://www.w3.org/2005/Atom'

DESCRIPTION_MAX = 500
BODY_LOCALNAMES = {'encoded'}  # full article bodies: always stripped

SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')
TAG_RE = re.compile(r'<[^>]+>')
IMG_TYPES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
             '.gif': 'image/gif', '.webp': 'image/webp'}


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _rfc822(dt):
    from email.utils import format_datetime
    return format_datetime(dt, usegmt=True)


def _iso_to_dt(text):
    """Best-effort ISO-8601 to aware datetime; None on failure."""
    try:
        dt = datetime.fromisoformat(text.strip().replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_to_rfc822(text):
    dt = _iso_to_dt(text or '')
    return _rfc822(dt) if dt else None


def html_to_teaser(text, limit=DESCRIPTION_MAX):
    """Strip HTML tags/entities, collapse whitespace, cap length with ellipsis."""
    if not text:
        return ''
    plain = html.unescape(TAG_RE.sub(' ', text))
    plain = re.sub(r'\s+', ' ', plain).strip()
    if len(plain) > limit:
        plain = plain[:limit].rsplit(' ', 1)[0].rstrip() + '…'
    return plain


def _image_type(url):
    path = url.split('?', 1)[0].lower()
    for ext, mime in IMG_TYPES.items():
        if path.endswith(ext):
            return mime
    return 'image/jpeg'


def _add_enclosure(item_el, image_url):
    if not image_url or not re.match(r'https?://', image_url):
        return
    enc = ET.SubElement(item_el, 'enclosure')
    enc.set('url', image_url)
    enc.set('type', _image_type(image_url))
    enc.set('length', '0')


def jsonfeed_to_rss(payload, site_name=None, site_url=None, lang=None, feed_url=None, now=None):
    """Build a normalized RSS 2.0 feed from `html2rss scrape --format jsonfeed`
    stdout (may have log lines before the JSON). Returns (xml_bytes, item_count).
    Raises on unparseable input or zero items."""
    if now is None:
        now = datetime.now(timezone.utc)
    start = payload.find(b'{') if isinstance(payload, bytes) else payload.find('{')
    if start < 0:
        raise ValueError('no JSON document in payload')
    data = json.loads(payload[start:])
    items = data.get('items') or []
    if not items:
        raise ValueError('jsonfeed has no items')

    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = (data.get('title') or site_name or 'feed').strip()
    ET.SubElement(channel, 'link').text = data.get('home_page_url') or site_url or ''
    if site_url and not data.get('home_page_url'):
        pass
    desc = (data.get('description') or '').strip()
    ET.SubElement(channel, 'description').text = desc or (data.get('title') or site_name or '')
    if lang:
        ET.SubElement(channel, 'language').text = lang
    ET.SubElement(channel, 'pubDate').text = _rfc822(now)
    if feed_url:
        link = ET.SubElement(channel, f'{{{ATOM_NS}}}link')
        link.set('href', feed_url)
        link.set('rel', 'self')
        link.set('type', 'application/rss+xml')

    for it in items[:25]:
        title = (it.get('title') or '').strip()
        url = (it.get('url') or it.get('external_url') or '').strip()
        if not title or not url:
            continue
        el = ET.SubElement(channel, 'item')
        ET.SubElement(el, 'title').text = title
        ET.SubElement(el, 'link').text = url
        teaser = html_to_teaser(it.get('content_text') or it.get('content_html') or it.get('summary') or '')
        if teaser:
            ET.SubElement(el, 'description').text = teaser
        pub = _iso_to_rfc822(it.get('date_published') or '')
        ET.SubElement(el, 'pubDate').text = pub or _rfc822(now)
        ET.SubElement(el, 'guid').text = (it.get('id') or url).strip()
        _add_enclosure(el, it.get('image') or it.get('banner_image'))

    n_items = len(channel.findall('item'))
    if n_items == 0:
        raise ValueError('no usable items (title+url) in jsonfeed')
    return ET.tostring(rss, encoding='UTF-8', xml_declaration=True), n_items


def strip_item_content(xml_bytes, feed_url=None, now=None):
    """Normalize an RSS 2.0 feed from `html2rss scrape` (fallback path):

    - full bodies (<content:encoded>) are removed; <description> is kept as a
      plain-text teaser capped at DESCRIPTION_MAX chars
    - channel keeps exactly one pubDate (dc:date is folded in or dropped)
    - every channel element sits before the first <item>
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
            local = _local(child.tag)
            if local in BODY_LOCALNAMES:
                item.remove(child)
            elif local == 'description':
                item.remove(child)
                teaser = html_to_teaser(child.text or '')
                if teaser:
                    d = ET.SubElement(item, 'description')
                    d.text = teaser
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
    """Return a list of problems; empty list means a valid RSS feed."""
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
        if item.find('pubDate') is None:
            problems.append(f'item {i}: missing pubDate')
        for enc in item.findall('enclosure'):
            if not re.match(r'https?://', enc.get('url') or ''):
                problems.append(f'item {i}: enclosure url is not http(s)')
        for child in list(item):
            local = child.tag.rsplit('}', 1)[-1]
            if local in BODY_LOCALNAMES:
                problems.append(f'item {i}: still contains <{local}> (no full-body policy)')
            if local == 'description' and len(child.text or '') > DESCRIPTION_MAX + 10:
                problems.append(f'item {i}: description over {DESCRIPTION_MAX} chars')
    return problems
