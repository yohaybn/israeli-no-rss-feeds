#!/usr/bin/env python3
"""Unit tests for feedlib + schema validation of the repo's sites.json. Stdlib only."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from feedlib import strip_item_content, validate_feed_bytes  # noqa: E402
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
<item><title>a</title><link>https://x.co.il/a</link><guid>a</guid></item>
</channel></rss>
'''

DIRTY_FEED = CLEAN_FEED.replace(
    b'<guid>a</guid>',
    b'<guid>a</guid><description>should not be here</description>')

failures = []


def check(name, cond):
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond:
        failures.append(name)


def main():
    stripped, n = strip_item_content(RAW_FEED.encode('utf-8'))
    check('strip keeps 2 items', n == 2)
    check('strip removes description', b'<description>full teaser' not in stripped
          and b'more text' not in stripped)
    check('strip removes content:encoded', b'encoded' not in stripped)
    check('strip keeps title', 'כתבה ראשונה'.encode() in stripped)
    check('strip keeps link and guid', b'https://example.co.il/1' in stripped)
    check('strip keeps channel description (channel-level ok)', b'channel desc' in stripped)

    check('clean feed validates', validate_feed_bytes(CLEAN_FEED) == [])
    dirty = validate_feed_bytes(DIRTY_FEED)
    check('dirty feed flagged', any('title+link policy' in p for p in dirty))
    check('non-xml flagged', validate_feed_bytes(b'not xml') != [])
    check('atom root flagged', validate_feed_bytes(b'<feed></feed>') != [])

    sites_problems = validate_feeds.validate_sites(os.path.join(ROOT, 'sites.json'))
    check('repo sites.json valid', sites_problems == [])
    for p in sites_problems:
        print('   sites.json:', p)

    print(f'{len(failures)} failure(s)')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
