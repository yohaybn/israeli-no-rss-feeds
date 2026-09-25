#!/usr/bin/env python3
"""Validate sites.json schema and/or generated feeds. Used by CI and tests.

  python3 scripts/validate_feeds.py --sites sites.json
  python3 scripts/validate_feeds.py --feeds-dir out/feeds
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feedlib import SLUG_RE, validate_feed_bytes  # noqa: E402

VALID_LANGS = {'he', 'ar', 'en'}


def validate_sites(path):
    problems = []
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return [f'{path}: cannot parse JSON: {e}']
    sites = data.get('sites')
    if not isinstance(sites, list) or not sites:
        return [f'{path}: missing non-empty "sites" list']
    seen = set()
    for i, s in enumerate(sites):
        if not isinstance(s, dict):
            problems.append(f'sites[{i}]: not an object')
            continue
        for key in ('slug', 'name', 'url'):
            if key not in s:
                problems.append(f'sites[{i}]: missing "{key}"')
        slug = s.get('slug', '')
        if not SLUG_RE.match(slug):
            problems.append(f'sites[{i}]: bad slug {slug!r} (use [a-z0-9-])')
        if slug in seen:
            problems.append(f'sites[{i}]: duplicate slug {slug!r}')
        seen.add(slug)
        url = s.get('url', '')
        if not url.startswith('https://'):
            problems.append(f'sites[{i}] ({slug}): url must start with https://')
        if s.get('lang', 'he') not in VALID_LANGS:
            problems.append(f'sites[{i}] ({slug}): lang must be one of {sorted(VALID_LANGS)}')
    return problems


def validate_feeds_dir(feeds_dir):
    problems = []
    if not os.path.isdir(feeds_dir):
        return [f'{feeds_dir}: not a directory']
    xmls = sorted(f for f in os.listdir(feeds_dir) if f.endswith('.xml'))
    if not xmls:
        return [f'{feeds_dir}: no .xml feeds found']
    for name in xmls:
        path = os.path.join(feeds_dir, name)
        with open(path, 'rb') as f:
            for p in validate_feed_bytes(f.read()):
                problems.append(f'{name}: {p}')
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sites', help='path to sites.json')
    ap.add_argument('--feeds-dir', help='directory of generated .xml feeds')
    args = ap.parse_args()
    problems = []
    if args.sites:
        problems += validate_sites(args.sites)
    if args.feeds_dir:
        problems += validate_feeds_dir(args.feeds_dir)
    if not args.sites and not args.feeds_dir:
        ap.error('pass --sites and/or --feeds-dir')
    for p in problems:
        print(f'FAIL {p}')
    print(f'{len(problems)} problem(s)')
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
