import os, sys, unittest, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from wordpress_feed import posts_to_rss, endpoint
from feedlib import validate_feed_bytes
SITE = {'name':'Example', 'url':'https://example.com/', 'wordpress_api':'https://example.com/wp-json/wp/v2/posts', 'lang':'he'}
POST = {'id':123, 'date_gmt':'2026-09-30T03:55:24', 'link':'https://example.com/story/', 'title':{'rendered':'A &amp; B'}, 'excerpt':{'rendered':'<p>'+'word '*300+'</p>'}, 'content':{'rendered':'SECRET FULL BODY'}}
class WordPressTest(unittest.TestCase):
    def test_preserves_dates_ids_and_teaser_only(self):
        rss,n = posts_to_rss([POST],SITE)
        self.assertEqual(n,1); self.assertEqual(validate_feed_bytes(rss),[])
        item=ET.fromstring(rss).find('channel/item')
        self.assertEqual(item.findtext('title'),'A & B')
        self.assertEqual(item.findtext('guid'),'https://example.com/?p=123')
        self.assertEqual(item.findtext('pubDate'),'Wed, 30 Sep 2026 03:55:24 GMT')
        self.assertLessEqual(len(item.findtext('description')),500)
        self.assertNotIn(b'SECRET',rss)
    def test_no_cross_host_or_fake_date(self):
        with self.assertRaises(ValueError): posts_to_rss([dict(POST,link='https://evil.example/a')],SITE)
        with self.assertRaises(ValueError): posts_to_rss([dict(POST,date_gmt='bad')],SITE)
        with self.assertRaises(ValueError): endpoint(dict(SITE,wordpress_api='https://other.example/posts'))
if __name__ == '__main__': unittest.main()
