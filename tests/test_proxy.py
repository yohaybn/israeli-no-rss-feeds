import os, sys, unittest
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from generate_feeds import source_request

class ProxyTest(unittest.TestCase):
    def test_no_config_uses_direct_request(self):
        with patch.dict(os.environ, {'TECH_IL_WORKER_URL': ''}):
            self.assertEqual(source_request('https://tech-il.co.il/robots.txt').full_url, 'https://tech-il.co.il/robots.txt')
    def test_only_tech_il_relayed_including_robots(self):
        with patch.dict(os.environ, {'TECH_IL_WORKER_URL': 'https://relay.test/'}):
            for source in ['https://tech-il.co.il/robots.txt', 'https://tech-il.co.il/wp-json/wp/v2/posts?per_page=25']:
                req = source_request(source)
                self.assertEqual(urlsplit(req.full_url).hostname, 'relay.test')
                self.assertEqual(parse_qs(urlsplit(req.full_url).query)['url'], [source])
            self.assertEqual(source_request('https://letsai.co.il/robots.txt').full_url, 'https://letsai.co.il/robots.txt')
    def test_bad_config_rejected(self):
        for relay in ['http://relay.test', 'https://user:pass@relay.test', 'https://relay.test/?q=x']:
            with patch.dict(os.environ, {'TECH_IL_WORKER_URL': relay}), self.assertRaises(ValueError):
                source_request('https://tech-il.co.il/robots.txt')
