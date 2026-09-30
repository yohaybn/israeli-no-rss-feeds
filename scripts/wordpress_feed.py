"""WordPress public REST listing -> RSS. Only headlines/links/short excerpts."""
import json
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit
from feedlib import html_to_teaser, jsonfeed_to_rss


def endpoint(site):
    source = site.get('wordpress_api') or site['url'].rstrip('/') + '/wp-json/wp/v2/posts'
    home = urlsplit(site['url'])
    parsed = urlsplit(source)
    if parsed.scheme != 'https' or parsed.netloc != home.netloc or parsed.query or parsed.fragment or parsed.path.rstrip('/') != '/wp-json/wp/v2/posts':
        raise ValueError('WordPress API must be HTTPS on the site hostname')
    return source + '?' + urlencode({
        'per_page': 25, 'orderby': 'date', 'order': 'desc',
        '_fields': 'id,date_gmt,link,title,excerpt'})


def posts_to_rss(posts, site, feed_url=None):
    if not isinstance(posts, list) or not posts:
        raise ValueError('WordPress REST unavailable or disabled: expected non-empty posts list')
    home = urlsplit(site['url'])
    items = []
    for post in posts[:25]:
        if not isinstance(post, dict) or not isinstance(post.get('title'), dict) or not isinstance(post['title'].get('rendered'), str) or not post['title']['rendered'].strip():
            raise ValueError('Not valid WordPress post JSON: missing rendered title')
        if not isinstance(post.get('date_gmt'), str):
            raise ValueError('Not valid WordPress post JSON: missing UTC date')
        link = post.get('link', '')
        if urlsplit(link).netloc != home.netloc or not link.startswith('https://'):
            raise ValueError('Post link outside publisher hostname')
        post_id = post.get('id')
        if not isinstance(post_id, int) or post_id <= 0:
            raise ValueError('Post requires positive publisher ID')
        # WordPress date_gmt has no suffix but is explicitly UTC, unlike site-local date.
        published = datetime.fromisoformat(post['date_gmt'].rstrip('Z')).replace(tzinfo=timezone.utc)
        items.append({'id': site['url'].rstrip('/') + '/?p=' + str(post_id),
                      'url': link, 'title': html_to_teaser(post.get('title', {}).get('rendered', ''), 1000),
                      'summary': html_to_teaser(post.get('excerpt', {}).get('rendered', '')),
                      'date_published': published.isoformat()})
    rss, count = jsonfeed_to_rss(json.dumps({'title': site['name'], 'home_page_url': site['url'],
                                     'items': items}).encode('utf-8'), site_name=site['name'],
                           site_url=site['url'], lang=site.get('lang'), feed_url=feed_url)
    # Publisher numeric IDs are identifiers, not article permalink GUIDs.
    import xml.etree.ElementTree as ET
    root = ET.fromstring(rss)
    for guid in root.findall('channel/item/guid'):
        guid.set('isPermaLink', 'false')
    return ET.tostring(root, encoding='UTF-8', xml_declaration=True), count
