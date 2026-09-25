#!/usr/bin/env python3
"""Unit tests for feedlib + schema validation of the repo's sites.json. Stdlib only."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from feedlib import (jsonfeed_to_rss, strip_item_content,  # noqa: E402
                     validate_feed_bytes)
import validate_feeds  # noqa: E402

RAW_FEED = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Test Site</title>
    <link>https://example.co.il</link>
    <description>channel desc</description>
    <item>
      <title>כתבה ראשונה</title>
      <link>https://example.co.il/1</link>
      <description>full teaser text that must be stripped</description>
      <content:encoded>&lt;p&gt;full article body&lt;/p&gt;</content:encoded>
      <pubDate>Fri, 25 Sep 2026 09:00:00 +0000</pubDate>
      <guid>https://example.co.il/1</guid>
    </item>
    <item>
      <title>כתבה שנייה</title>
      <link>https://example.co.il/2</link>
      <description>more text</description>
      <guid>2</guid>
    </item>
  </channel>
</rss>
'''

CLEAN_FEED = b'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>T</title><link>https://x.co.il</link>
<item><title>a</title><link>https://x.co.il/a</link><guid>a</guid><pubDate>Fri, 25 Sep 2026 09:00:00 +0000</pubDate></item>
</channel></rss>
'''

DIRTY_FEED = CLEAN_FEED.replace(
    b'<guid>a</guid>',
    b'<guid>a</guid><content:encoded xmlns:content="http://purl.org/rss/1.0/modules/content/">full body</content:encoded>')

failures = []


def check(name, cond):
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond:
        failures.append(name)


def _raises(fn):
    try:
        fn()
        return False
    except Exception:
        return True


def jf_empty():
    jsonfeed_to_rss(b'{"items":[]}')


def main():
    stripped, n = strip_item_content(RAW_FEED.encode('utf-8'))
    check('strip keeps 2 items', n == 2)
    check('strip keeps description as teaser', b'full teaser text that must be stripped' in stripped
          and b'more text' in stripped)
    check('strip removes content:encoded', b'full article body' not in stripped)
    check('strip keeps title', 'כתבה ראשונה'.encode() in stripped)
    check('strip keeps link and guid', b'https://example.co.il/1' in stripped)
    check('strip keeps channel description (channel-level ok)', b'channel desc' in stripped)

    check('clean feed validates', validate_feed_bytes(CLEAN_FEED) == [])
    dirty = validate_feed_bytes(DIRTY_FEED)
    check('dirty feed flagged', any('no full-body policy' in p for p in dirty))
    check('non-xml flagged', validate_feed_bytes(b'not xml') != [])
    check('atom root flagged', validate_feed_bytes(b'<feed></feed>') != [])

    # jsonfeed -> rss: real dates, teaser cap, enclosure
    jf = b'{"title":"T","home_page_url":"https://x.co.il","items":['          b'{"id":"1","url":"https://x.co.il/1","title":"t1","date_published":"2026-09-20T10:00:00+03:00",'          b'"content_html":"<p>' + b'a' * 900 + b'</p>","image":"https://x.co.il/i.png?w=1"},'          b'{"id":"2","url":"https://x.co.il/2","title":"t2"}]}'
    built, bn = jsonfeed_to_rss(jf, site_name='T', site_url='https://x.co.il', lang='he',
                                feed_url='https://f.example/t.xml',
                                now=__import__('datetime').datetime(2026, 9, 25, tzinfo=__import__('datetime').timezone.utc))
    check('jsonfeed builds 2 items', bn == 2)
    check('jsonfeed real date kept', b'Sun, 20 Sep 2026 07:00:00' in built)
    check('jsonfeed backfill date', b'Fri, 25 Sep 2026 00:00:00' in built)
    check('jsonfeed enclosure', b'<enclosure url="https://x.co.il/i.png?w=1" type="image/png"' in built)
    check('jsonfeed teaser capped', b'a' * 600 not in built and b'aaa' in built)
    check('built feed validates', validate_feed_bytes(built) == [])
    check('jsonfeed empty items raises', _raises(jf_empty))

    sites_problems = validate_feeds.validate_sites(os.path.join(ROOT, 'sites.json'))
    check('repo sites.json valid', sites_problems == [])
    for p in sites_problems:
        print('   sites.json:', p)

    print(f'{len(failures)} failure(s)')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
