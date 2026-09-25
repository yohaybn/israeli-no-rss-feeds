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
import os
import subprocess
import sys
import time
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feedlib import strip_item_content, validate_feed_bytes  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get('OUT_DIR', os.path.join(ROOT, 'out'))
UA = 'israeli-no-rss-feeds (+https://github.com/yohay-ai/israeli-no-rss-feeds)'
SCRAPE_TIMEOUT = 120
POLITENESS_DELAY = 2  # seconds between sites


def robots_allows(url):
    """Check robots.txt for the page URL. Unreachable robots.txt means allowed."""
    from urllib.parse import urlparse
    p = urlparse(url)
    robots_url = f'{p.scheme}://{p.netloc}/robots.txt'
    rp = urllib.robotparser.RobotFileParser()
    try:
        req = urllib.request.Request(robots_url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            rp.parse(r.read().decode('utf-8', 'ignore').splitlines())
    except Exception:
        return True, 'robots.txt unreachable, allowed by default'
    for agent in ('html2rss', '*'):
        if not rp.can_fetch(agent, url):
            return False, f'robots.txt disallows {url} for agent {agent!r}'
    return True, 'robots.txt allows'


def generate_site(site):
    """Return (result_dict, clean_feed_bytes_or_None)."""
    url = site['url']
    allowed, reason = robots_allows(url)
    if not allowed:
        return {'status': 'skipped', 'reason': reason}, None
    try:
        proc = subprocess.run(
            ['html2rss', 'scrape', url, '--limit', '25'],
            capture_output=True, timeout=SCRAPE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {'status': 'failed', 'reason': f'html2rss timed out ({SCRAPE_TIMEOUT}s)'}, None
    if proc.returncode != 0 or not proc.stdout.strip():
        err = proc.stderr.decode('utf-8', 'ignore').strip().splitlines()
        tail = err[-1][:300] if err else f'exit {proc.returncode}, empty output'
        return {'status': 'failed', 'reason': tail}, None
    try:
        cleaned, n_items = strip_item_content(proc.stdout)
    except Exception as e:
        return {'status': 'failed', 'reason': f'feed post-processing failed: {e}'}, None
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
            stat = '⏭️ נדחה ע"י robots.txt'
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
<p>פידי RSS (כותרת + קישור בלבד) לאתרים ישראליים מובילים שאין להם RSS משלהם.
מתחדש אוטומטית כל 15 דקות דרך GitHub Actions עם
<a href="https://github.com/html2rss/html2rss">html2rss</a> (חילוץ אוטומטי, בלי סקרייפר פר-אתר).
קוד המקור: <a href="https://github.com/yohay-ai/israeli-no-rss-feeds">github.com/yohay-ai/israeli-no-rss-feeds</a></p>
<p>עדכון אחרון: {status['generated_at']} · נוצרו {status['ok_count']}/{status['total']} פידים</p>
<table>
<tr><th>אתר</th><th>כתובת</th><th>סטטוס</th><th>פיד</th></tr>
{''.join(rows)}
</table>
<p>גישה ישירה: <code>{base_url}/feeds/&lt;slug&gt;.xml</code> · סטטוס מכונה: <a href="status.json">status.json</a></p>
</body>
</html>
"""


def main():
    with open(os.path.join(ROOT, 'sites.json'), encoding='utf-8') as f:
        sites = json.load(f)['sites']
    feeds_dir = os.path.join(OUT, 'feeds')
    os.makedirs(feeds_dir, exist_ok=True)

    base_url = os.environ.get('FEEDS_BASE_URL', 'https://yohay-ai.github.io/israeli-no-rss-feeds')
    status = {'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
              'base_url': base_url, 'sites': []}
    ok_count = 0

    for site in sites:
        print(f"== {site['slug']}: {site['url']}", flush=True)
        res, xml_bytes = generate_site(site)
        entry = {'slug': site['slug'], 'name': site['name'], 'url': site['url'],
                 'lang': site.get('lang', 'he'), 'category': site.get('category', 'news'),
                 **res}
        if xml_bytes is not None:
            with open(os.path.join(feeds_dir, f"{site['slug']}.xml"), 'wb') as f:
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
