"""Calcalist public category listings -> RSS; never fetch article bodies/paywalls."""
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from feedlib import jsonfeed_to_rss


def widget_data(payload, widget):
    soup = BeautifulSoup(payload, 'html.parser')
    marker = "'" + widget + "',"
    for script in soup.find_all('script'):
        text = script.get_text()
        if marker in text:
            return json.JSONDecoder().raw_decode(text.split(marker, 1)[1].lstrip())[0]
    raise ValueError('Required public listing widget missing')


def json_listing_html(data):
    """Normalize public JSON listing metadata into the same parser, no article body."""
    articles = []
    for a in data.get('data', []):
        articles.append({'title': a.get('title'), 'publishedLink': a.get('publishedLink'),
                         'subTitle': a.get('subTitle', a.get('sub_title', '')),
                         'launchDate': a.get('launchDate', a.get('launch_date')),
                         'promotionImageDetails': a.get('promotionImageDetails', {'publishedLink': a.get('path', '')})})
    return ("<script>window.YITSiteWidgets.push(['public','SiteArticleHeadlinesComponenta'," +
            json.dumps({'firstPageArticles': articles}) + "]);</script>").encode()

def listing_to_rss(payload, site, feed_url=None):
    soup = BeautifulSoup(payload, 'html.parser')
    # Global news ticker and recommendations are not the selected category.
    for node in soup.select('.TwentyFourSevenComponenta, .TaboolaComponenta, header, footer, nav'):
        node.decompose()
    # Public JSON embedded for the category's client-side headline listing.
    # Read only listing metadata, never execute scripts or copy article bodies.
    embedded = []
    decoder = json.JSONDecoder()
    for script in soup.find_all('script'):
        text = script.get_text()
        marker = next((m for m in ["'SiteArticleHeadlinesComponenta',", "'SitePhotoArchiveComponenta',", "'SiteMusafArchiveComponenta',", "'PodcastCategoryComponenta',", "'PodcastArchiveComponenta',", "'CartoonArchiveComponenta',"] if m in text), None)
        if not marker:
            continue
        try:
            data, _ = decoder.raw_decode(text.split(marker, 1)[1].lstrip())
            embedded.extend(data.get('firstPageArticles', data.get('extraData', [])))
        except (ValueError, TypeError):
            continue
    items = []
    seen = set()
    for article in embedded:
        link = article.get('publishedLink', '')
        if not ((urlsplit(link).scheme == 'https' and urlsplit(link).hostname == 'www.calcalist.co.il' and any(p in urlsplit(link).path for p in ['/article/', '/articles/'])) or
                (site['url'].endswith('/supplement') and urlsplit(link).hostname == 'musafim.webflow.io' and link.startswith('https://'))):
            continue
        if link in seen or not article.get('title'):
            continue
        seen.add(link)
        item = {'id': link, 'url': link, 'title': article['title'], 'summary': article.get('subTitle', '')[:500]}
        date = article.get('launchDate')
        if date:
            try:
                item['date_published'] = datetime.fromisoformat(date.replace('Z', '+00:00')).isoformat()
            except ValueError:
                pass
        image = (article.get('promotionImageDetails') or {}).get('publishedLink', '')
        if image.startswith('https://pic1.calcalist.co.il/'):
            item['image'] = image
        items.append(item)
    for slot in soup.select('.slotView, .slot-view'):
        if len(items) >= 25:
            break
        title = slot.select_one('.slotTitle, .slot-title')
        if not title:
            continue
        link_node = title if title.name == 'a' else title.find('a', href=True)
        if not link_node:
            continue
        link = urljoin(site['url'], link_node.get('href', '')).split('#')[0]
        parsed = urlsplit(link)
        if parsed.hostname != 'www.calcalist.co.il' or parsed.scheme != 'https' or not any(p in parsed.path for p in ['/article/', '/articles/']):
            continue
        text = title.get_text(' ', strip=True)
        if not text or link in seen:
            continue
        seen.add(link)
        item = {'id': link, 'url': link, 'title': text}
        teaser = slot.select_one('.slotSubTitle')
        if teaser:
            item['summary'] = teaser.get_text(' ', strip=True)[:500]
        date = slot.select_one('.dateView, .date-view')
        match = re.search(r'\b(\d{2}\.\d{2}\.(?:\d{4}|\d{2}))\b', date.get_text() if date else '')
        if match:
            try:
                item['date_published'] = datetime.strptime(match[1], '%d.%m.%Y' if len(match[1]) == 10 else '%d.%m.%y').replace(tzinfo=ZoneInfo('Asia/Jerusalem')).isoformat()
            except ValueError:
                pass
        image = slot.select_one('img[src]')
        if image:
            src = urljoin(site['url'], image['src'])
            if urlsplit(src).hostname == 'pic1.calcalist.co.il' and src.startswith('https://'):
                item['image'] = src
        items.append(item)
        if len(items) == 25:
            break
    if not items:
        raise ValueError('No public category article cards found; page may not be an article category')
    return jsonfeed_to_rss(json.dumps({'title': site['name'], 'home_page_url': site['url'], 'items': items[:25]}).encode(),
                           site_name=site['name'], site_url=site['url'], lang='he', feed_url=feed_url)
