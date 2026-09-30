import os,sys,json,unittest,xml.etree.ElementTree as ET
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','scripts'))
from calcalist_feed import listing_to_rss
from feedlib import validate_feed_bytes
SITE={'name':'כלכליסט - משפט','url':'https://www.calcalist.co.il/local_news/category/3772'}
ARTICLE={'title':'Public title','publishedLink':'https://www.calcalist.co.il/local_news/article/test', 'launchDate':'2026-09-30T12:34:56Z','subTitle':'x'*700,'body':'SECRET BODY'}
def page(a): return ("<script>window.YITSiteWidgets.push(['x','SiteArticleHeadlinesComponenta',"+json.dumps({'categoryId':'3772','firstPageArticles':a})+"]);</script>").encode()
class CalcalistTest(unittest.TestCase):
 def test_public_metadata_only_and_real_date(self):
  rss,n=listing_to_rss(page([ARTICLE]),SITE);self.assertEqual(n,1);self.assertEqual(validate_feed_bytes(rss),[])
  self.assertNotIn(b'SECRET',rss);item=ET.fromstring(rss).find('channel/item');self.assertLessEqual(len(item.findtext('description')),500);self.assertEqual(item.findtext('pubDate'),'Wed, 30 Sep 2026 12:34:56 GMT')
 def test_cross_host_and_duplicate_rejected(self):
  rss,n=listing_to_rss(page([ARTICLE,ARTICLE,dict(ARTICLE,publishedLink='https://evil.test/article/test')]),SITE);self.assertEqual(n,1)
 def test_global_ticker_is_not_category_content(self):
  with self.assertRaises(ValueError): listing_to_rss(b'<div class="TwentyFourSevenComponenta"><div class="slotView"><a class="slotTitle" href="https://www.calcalist.co.il/market/article/test">Unrelated global news</a></div></div>',SITE)
 def test_dom_card_with_date(self):
  rss,n=listing_to_rss(b'<div class="slotView"><a class="slotTitle" href="https://www.calcalist.co.il/market/article/test">Title</a><span class="dateView">30.09.26</span></div>',SITE);self.assertEqual(n,1);self.assertIn(b'Tue, 29 Sep 2026 21:00:00',rss)
 def test_empty_page_does_not_publish_fake_feed(self):
  with self.assertRaises(ValueError): listing_to_rss(b'<html>Challenge</html>',SITE)

 def test_special_json_listing_and_image(self):
  from calcalist_feed import json_listing_html
  rss,n=listing_to_rss(json_listing_html({'data':[dict(ARTICLE,path='https://pic1.calcalist.co.il/image.jpg')]}),SITE)
  self.assertEqual(n,1);self.assertEqual(validate_feed_bytes(rss),[])
 def test_legacy_articles_supported(self):
  rss,n=listing_to_rss(page([dict(ARTICLE,publishedLink='https://www.calcalist.co.il/articles/0,7340,L-3949191,00.html')]),SITE);self.assertEqual(n,1)
