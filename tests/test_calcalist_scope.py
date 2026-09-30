import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from generate_feeds import prune_unconfigured_calcalist

class CalcalistScopeTests(unittest.TestCase):
    def test_only_main_categories_configured(self):
        sites = json.loads((ROOT / 'sites.json').read_text())['sites']
        expected = {'calcalist-home', 'calcalist-allnews', 'calcalist-buzz',
                    'calcalist-market', 'calcalist-calcalistech', 'calcalist-local-news',
                    'calcalist-real-estate', 'calcalist-world-news', 'calcalist-3772',
                    'calcalist-car', 'calcalist-style', 'calcalist-supplement', 'calcalist-5494'}
        self.assertEqual({s['slug'] for s in sites if s['slug'].startswith('calcalist')}, expected)

    def test_pruning_keeps_active_last_good_and_other_publishers(self):
        with tempfile.TemporaryDirectory() as directory:
            for filename in ['calcalist-home.xml', 'calcalist-tv.xml', 'calcalist.xml',
                             'calcalist-tech.xml', 'tech-il.xml', 'calcalist-note.txt']:
                Path(directory, filename).write_text('last-good')
            removed = prune_unconfigured_calcalist(directory, [{'slug': 'calcalist-home'}])
            self.assertEqual(set(removed), {'calcalist-tv.xml', 'calcalist.xml', 'calcalist-tech.xml'})
            self.assertEqual(Path(directory, 'calcalist-home.xml').read_text(), 'last-good')
            self.assertTrue(Path(directory, 'tech-il.xml').exists())
            self.assertTrue(Path(directory, 'calcalist-note.txt').exists())
