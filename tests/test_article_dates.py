import os, sys, unittest, xml.etree.ElementTree as ET
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from article_dates import parse_article_date, correct_batch_dates, suspicious_urls

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
BIZPORTAL = '''<html><head>
<meta property="article:published_time" content="2026-10-01T09:04:00Z" />
<script type="application/ld+json">{"@type":"NewsArticle","datePublished": "2026-10-01T12:04:00+03:00"}</script>
</head></html>'''


def feed(items):
    body = ''.join(f'<item><title>t{i}</title><link>https://x.co.il/{i}</link>'
                   + (f'<pubDate>{d}</pubDate>' if d else '') + '</item>' for i, d in enumerate(items))
    return f'<rss version="2.0"><channel><title>T</title>{body}</channel></rss>'.encode()


SCAN = 'Fri, 02 Oct 2026 07:14:41 GMT'


class ParseTest(unittest.TestCase):
    def test_meta_published_time(self):
        self.assertEqual(parse_article_date(BIZPORTAL, NOW), datetime(2026, 10, 1, 9, 4, tzinfo=timezone.utc))
    def test_json_ld_with_offset(self):
        page = '<script type="application/ld+json">{"@graph":[{"datePublished":"2026-09-30T20:30:00+03:00"}]}</script>'
        self.assertEqual(parse_article_date(page, NOW), datetime(2026, 9, 30, 17, 30, tzinfo=timezone.utc))
    def test_attribute_order_and_itemprop(self):
        page = '<meta content="2026-09-29T10:00:00+00:00" itemprop="datePublished">'
        self.assertEqual(parse_article_date(page, NOW), datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc))
    def test_future_and_missing_dates_rejected(self):
        self.assertIsNone(parse_article_date('<meta property="article:published_time" content="2027-01-01T00:00:00Z">', NOW))
        self.assertIsNone(parse_article_date('<html>no date</html>', NOW))
        self.assertIsNone(parse_article_date('<meta property="article:published_time" content="garbage">', NOW))


class CorrectionTest(unittest.TestCase):
    def test_only_clustered_or_missing_dates_are_fetched(self):
        xml = feed([SCAN, SCAN, SCAN, 'Wed, 30 Sep 2026 07:47:13 GMT', None])
        got = [ET.tostring(i).decode() for i in suspicious_urls(ET.fromstring(xml))]
        self.assertEqual(len(got), 4)  # 3 clustered + 1 missing, the unique real date is left alone
    def test_batch_dates_replaced_by_page_dates(self):
        xml = feed([SCAN] * 3 + ['Wed, 30 Sep 2026 07:47:13 GMT'])
        calls = []
        def fetch(url):
            calls.append(url); return BIZPORTAL
        out, n = correct_batch_dates(xml, fetch, now=NOW)
        dates = [i.findtext('pubDate') for i in ET.fromstring(out).findall('./channel/item')]
        self.assertEqual(n, 3)
        self.assertEqual(dates[:3], ['Thu, 01 Oct 2026 09:04:00 GMT'] * 3)
        self.assertEqual(dates[3], 'Wed, 30 Sep 2026 07:47:13 GMT')
        self.assertEqual(len(calls), 3)
    def test_failed_fetch_keeps_existing_date(self):
        xml = feed([SCAN] * 3)
        out, n = correct_batch_dates(xml, lambda url: None, now=NOW)
        self.assertEqual((out, n), (xml, 0))
        def boom(url): raise OSError('down')
        self.assertEqual(correct_batch_dates(xml, boom, now=NOW), (xml, 0))
    def test_fetch_cap_and_idempotence(self):
        xml = feed([SCAN] * 5)
        out, n = correct_batch_dates(xml, lambda u: BIZPORTAL, max_fetch=2, now=NOW)
        self.assertEqual(n, 2)
        again, n2 = correct_batch_dates(out, lambda u: BIZPORTAL, max_fetch=10, now=NOW)
        self.assertEqual(n2, 3)  # remaining batch items; fixed ones now differ from the cluster
    def test_no_cluster_no_fetch(self):
        xml = feed(['Wed, 30 Sep 2026 07:47:13 GMT', 'Thu, 01 Oct 2026 09:14:46 GMT'])
        def fetch(url): raise AssertionError('should not fetch')
        self.assertEqual(correct_batch_dates(xml, fetch, now=NOW), (xml, 0))


if __name__ == '__main__':
    unittest.main()
