#!/usr/bin/env python3
"""Generate RSS feeds for Israeli sites that have none, via html2rss auto-source.

Reads sites.json, runs `html2rss scrape <url>` for each site, strips article
content (title+link only policy), and writes:
  out/feeds/<slug>.xml  - one feed per working site
  out/status.json       - machine-readable per-site status
  out/index.html        - human-readable status page (served by GitHub Pages)

One site's failure never fails the run: failed sites keep their previously
published feed (the workflow clones gh-pages into out/ before running).
Exits non-zero only when every site failed.
"""
import json
import html
import os
import subprocess
import sys
import time
import urllib.request
import urllib.robotparser
from urllib.parse import urlsplit, urlencode
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wordpress_feed import endpoint as wordpress_endpoint, posts_to_rss
from article_dates import correct_batch_dates  # noqa: E402
from feedlib import jsonfeed_to_rss, preserve_item_dates, strip_item_content, validate_feed_bytes  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get('OUT_DIR', os.path.join(ROOT, 'out'))
UA = 'israeli-no-rss-feeds (+https://github.com/yohaybn/israeli-no-rss-feeds)'
SCRAPE_TIMEOUT = 120
POLITENESS_DELAY = 2  # seconds between sites


def source_request(url):
    """Relay TECH-IL only when configured; never forward credentials or other sites."""
    relay = os.environ.get('TECH_IL_WORKER_URL', '').strip()
    if relay and urlsplit(url).netloc == 'tech-il.co.il':
        parsed = urlsplit(relay)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('TECH_IL_WORKER_URL must be a plain HTTPS endpoint')
        url = relay.rstrip('/') + '/?' + urlencode({'url': url})
    return urllib.request.Request(url, headers={'User-Agent': UA})


def robots_allows(url):
    """Check robots.txt for the page URL. Unreachable robots.txt means allowed."""
    from urllib.parse import urlparse
    p = urlparse(url)
    robots_url = f'{p.scheme}://{p.netloc}/robots.txt'
    rp = urllib.robotparser.RobotFileParser()
    try:
        req = source_request(robots_url)
        with urllib.request.urlopen(req, timeout=15) as r:
            rp.parse(r.read().decode('utf-8', 'ignore').splitlines())
    except Exception:
        return True, 'robots.txt unreachable, allowed by default'
    for agent in ('html2rss', '*'):
        if not rp.can_fetch(agent, url):
            return False, f'robots.txt disallows {url} for agent {agent!r}'
    return True, 'robots.txt allows'



def fetch_article(url):
    """Article page text for date lookup; None when robots.txt disallows or the fetch fails."""
    allowed, _ = robots_allows(url)
    if not allowed:
        return None
    with urllib.request.urlopen(source_request(url), timeout=20) as response:
        return response.read(2_000_000).decode('utf-8', 'ignore')


def extract_xml(payload):
    """Slice the XML document out of html2rss stdout (it may prepend log lines)."""
    for marker in (b'<?xml', b'<rss', b'<feed'):
        start = payload.find(marker)
        if start >= 0:
            return payload[start:]
    raise ValueError('no XML document in html2rss output: %r' % payload[:150])


def _scrape(url, extra_args):
    return subprocess.run(
        ['html2rss', 'scrape', url, '--limit', '25'] + extra_args,
        capture_output=True, timeout=SCRAPE_TIMEOUT)


def generate_site(site, feed_url=None):
    """Return (result_dict, clean_feed_bytes_or_None).

    Primary path: JSON Feed mode, rebuilt into RSS with real dates, plain-text
    teasers and image enclosures. Fallback: RSS mode normalized the old way.
    """
    url = site['url']
    allowed, reason = robots_allows(url)
    if not allowed:
        return {'status': 'skipped', 'reason': reason}, None
    if site.get('generator') == 'calcalist':
        try:
            from calcalist_feed import listing_to_rss, widget_data, json_listing_html
            request = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
            special = site.get('calcalist_listing')
            if special:
                if special == 'allnews':
                    today = datetime.now(__import__('zoneinfo').ZoneInfo('Asia/Jerusalem')).strftime('%Y-%m-%d')
                    source = 'https://www.calcalist.co.il/iphone/json/api/twenty_four_seven_wide/1/50/1/0/0/' + today
                elif special == 'buzz':
                    config = widget_data(payload, 'SiteCtechWideBuzzComponenta')
                    source = 'https://www.calcalist.co.il/iphone/json/api/calcalist_buzz_wide/' + config['componentaId'] + '/1/1/0/0/0'
                elif special == 'tv':
                    config = widget_data(payload, 'SiteVideoArchiveComponenta')
                    today = datetime.now(__import__('zoneinfo').ZoneInfo('Asia/Jerusalem')).strftime('%Y-%m-%d')
                    source = 'https://www.calcalist.co.il/iphone/json/api/article_list/' + config['componentaId'] + '/id/1/startDate/1992-04-01/endDate/' + today + '/pageNumber/0'
                else:
                    raise ValueError('Unknown Calcalist listing')
                allowed, reason = robots_allows(source)
                if not allowed:
                    return {'status': 'skipped', 'reason': reason}, None
                with urllib.request.urlopen(urllib.request.Request(source, headers={'User-Agent': UA}), timeout=30) as response:
                    payload = json_listing_html(json.load(response))
            cleaned, count = listing_to_rss(payload, site, feed_url)
            problems = validate_feed_bytes(cleaned)
            if problems:
                raise ValueError('; '.join(problems[:3]))
            return {'status': 'ok', 'items': count}, cleaned
        except Exception as error:
            return {'status': 'failed', 'reason': 'Calcalist listing unavailable/invalid: ' + str(error)[:250]}, None
    if site.get('generator') == 'wordpress' or site.get('wordpress_api'):
        try:
            api = wordpress_endpoint(site)
            allowed, reason = robots_allows(api)
            if not allowed:
                return {'status': 'skipped', 'reason': reason}, None
            request = source_request(api)
            with urllib.request.urlopen(request, timeout=30) as response:
                posts = json.load(response)
            cleaned, count = posts_to_rss(posts, site, feed_url)
            problems = validate_feed_bytes(cleaned)
            if problems:
                raise ValueError('; '.join(problems[:3]))
            return {'status': 'ok', 'items': count}, cleaned
        except Exception as error:
            return {'status': 'skipped', 'reason': 'WordPress REST unavailable/disabled or invalid: ' + str(error)[:250]}, None
    try:
        proc = _scrape(url, ['--format', 'jsonfeed'])
    except subprocess.TimeoutExpired:
        return {'status': 'failed', 'reason': f'html2rss timed out ({SCRAPE_TIMEOUT}s)'}, None
    cleaned = n_items = None
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            cleaned, n_items = jsonfeed_to_rss(
                proc.stdout, site_name=site.get('name'), site_url=url,
                lang=site.get('lang'), feed_url=feed_url)
        except Exception:
            cleaned = None
    if cleaned is None:
        # fallback: RSS mode
        try:
            proc = _scrape(url, [])
        except subprocess.TimeoutExpired:
            return {'status': 'failed', 'reason': f'html2rss timed out ({SCRAPE_TIMEOUT}s)'}, None
        if proc.returncode != 0 or not proc.stdout.strip():
            err = proc.stderr.decode('utf-8', 'ignore').strip().splitlines()
            tail = err[-1][:300] if err else f'exit {proc.returncode}, empty output'
            return {'status': 'failed', 'reason': tail}, None
        try:
            cleaned, n_items = strip_item_content(extract_xml(proc.stdout), feed_url=feed_url)
        except Exception as e:
            head = proc.stdout[:150].decode('utf-8', 'ignore').strip()
            return {'status': 'failed', 'reason': f'feed post-processing failed: {e} | stdout head: {head}'}, None
    problems = validate_feed_bytes(cleaned)
    if problems:
        return {'status': 'failed', 'reason': 'invalid feed: ' + '; '.join(problems[:3])}, None
    return {'status': 'ok', 'items': n_items}, cleaned


def write_index_html(status, base_url):
    rows = []
    for s in status['sites']:
        if s['status'] == 'ok':
            stat = f"✅ {s.get('items', 0)} פריטים"
            feed = f'<a href="feeds/{s["slug"]}.xml">feeds/{s["slug"]}.xml</a>'
        elif s['status'] == 'skipped':
            stat = '⏭️ ' + html.escape(s.get('reason', 'skipped')[:120])
            feed = ''
        else:
            stat = f'❌ {s.get("reason", "")[:80]}'
            feed = ''
        rows.append(
            f'<tr class="{s["status"]}"><td>{s["name"]}</td>'
            f'<td><a href="{s["url"]}">{s["url"]}</a></td><td>{stat}</td><td>{feed}</td></tr>')
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>israeli-no-rss-feeds - פידי RSS לאתרים ישראליים בלי RSS</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 2em auto; padding: 0 1em; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #ddd; padding: 6px 10px; text-align: right; font-size: 14px; }}
tr.failed td {{ color: #a00; }}
tr.ok td {{ color: #060; }}
code {{ background: #f4f4f4; padding: 1px 4px; }}
</style>
</head>
<body>
<h1>israeli-no-rss-feeds</h1>
<p>פידי RSS (כותרת, קישור, תקציר קצר ותמונה כשזמינים) לאתרים ישראליים מובילים שאין להם RSS משלהם.
מתחדש אוטומטית כל 30 דקות דרך GitHub Actions עם
<a href="https://github.com/html2rss/html2rss">html2rss</a> (חילוץ אוטומטי, בלי סקרייפר פר-אתר).
קוד המקור: <a href="https://github.com/yohaybn/israeli-no-rss-feeds">github.com/yohaybn/israeli-no-rss-feeds</a></p>
<p>עדכון אחרון: {status['generated_at']} · נוצרו {status['ok_count']}/{status['total']} פידים</p>
<table>
<tr><th>אתר</th><th>כתובת</th><th>סטטוס</th><th>פיד</th></tr>
{''.join(rows)}
</table>
<p>גישה ישירה: <code>{base_url}/feeds/&lt;slug&gt;.xml</code> · סטטוס מכונה: <a href="status.json">status.json</a></p>
<p>רוצים פיד לאתר נוסף? <a href="https://github.com/yohaybn/israeli-no-rss-feeds/issues/new?template=feed-request.yml">פתחו בקשת פיד</a> - המערכת מנסה לבנות אותו אוטומטית ופותחת PR.</p>
</body>
</html>
"""


def prune_unconfigured_calcalist(feeds_dir, sites):
    """Remove retired Calcalist files only, retaining last-good active feeds."""
    keep = {site['slug'] + '.xml' for site in sites}
    removed = []
    for filename in os.listdir(feeds_dir):
        if filename.startswith('calcalist') and filename.endswith('.xml') and filename not in keep:
            os.remove(os.path.join(feeds_dir, filename))
            removed.append(filename)
    return removed


def is_scraped(site):
    """Feeds built from html2rss scans, the only ones that can carry scan-time dates."""
    return not site.get('generator') and not site.get('wordpress_api')


def main():
    with open(os.path.join(ROOT, 'sites.json'), encoding='utf-8') as f:
        sites = json.load(f)['sites']
    feeds_dir = os.path.join(OUT, 'feeds')
    os.makedirs(feeds_dir, exist_ok=True)
    for filename in prune_unconfigured_calcalist(feeds_dir, sites):
        print(f'Removed retired Calcalist feed: {filename}', flush=True)

    base_url = os.environ.get('FEEDS_BASE_URL', 'https://yohaybn.github.io/israeli-no-rss-feeds')
    status = {'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
              'base_url': base_url, 'sites': []}
    ok_count = 0

    for site in sites:
        print(f"== {site['slug']}: {site['url']}", flush=True)
        res, xml_bytes = generate_site(site, feed_url=f'{base_url}/feeds/{site["slug"]}.xml')
        entry = {'slug': site['slug'], 'name': site['name'], 'url': site['url'],
                 'lang': site.get('lang', 'he'), 'category': site.get('category', 'news'),
                 **res}
        if xml_bytes is not None:
            feed_path = os.path.join(feeds_dir, f"{site['slug']}.xml")
            if os.path.isfile(feed_path):
                with open(feed_path, 'rb') as previous:
                    xml_bytes = preserve_item_dates(xml_bytes, previous.read())
            if is_scraped(site):
                xml_bytes, corrected = correct_batch_dates(xml_bytes, fetch_article)
                if corrected:
                    print(f'   corrected {corrected} scan-time dates from article pages', flush=True)
            with open(feed_path, 'wb') as f:
                f.write(xml_bytes)
            entry['feed'] = f'{base_url}/feeds/{site["slug"]}.xml'
            ok_count += 1
            print(f"   ok: {res.get('items')} items", flush=True)
        else:
            print(f"   {res['status']}: {res.get('reason', '')[:120]}", flush=True)
        status['sites'].append(entry)
        time.sleep(POLITENESS_DELAY)

    status['ok_count'] = ok_count
    status['total'] = len(sites)
    with open(os.path.join(OUT, 'status.json'), 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(write_index_html(status, base_url))

    print(f"DONE: {ok_count}/{len(sites)} feeds generated")
    sys.exit(0 if ok_count else 1)


if __name__ == '__main__':
    main()
