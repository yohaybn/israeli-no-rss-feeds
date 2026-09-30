#!/usr/bin/env python3
"""Deploy the narrow relay with a scoped Cloudflare token. Never print the token."""
import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path

BASE = 'https://api.cloudflare.com/client/v4'
NAME = 'tech-il-feed-relay'


def main():
    account = os.environ['CLOUDFLARE_ACCOUNT_ID'].strip()
    token = os.environ['CLOUDFLARE_API_TOKEN'].strip()
    if not re.fullmatch(r'[a-fA-F0-9]{32}', account):
        raise SystemExit('Cloudflare account ID must be 32 hex characters')

    def call(path, method='GET', body=None, content_type='application/json'):
        req = urllib.request.Request(BASE + path, data=body, method=method,
                                     headers={'Authorization': 'Bearer ' + token, 'Content-Type': content_type})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                result = json.load(r)
        except urllib.error.HTTPError as e:
            # Do not echo request headers or raw Cloudflare responses.
            raise SystemExit(f'Cloudflare API returned HTTP {e.code} for {method} {path}') from None
        if not result.get('success'):
            raise SystemExit('Cloudflare operation failed; check token scope/account')
        return result['result']

    prefix = f'/accounts/{account}/workers'
    subdomain = call(prefix + '/subdomain').get('subdomain')
    if not subdomain or not re.fullmatch(r'[a-z0-9-]+', subdomain):
        raise SystemExit('Set up the free workers.dev subdomain in Workers & Pages first')
    script = Path(__file__).resolve().parent.parent / 'worker/index.mjs'
    boundary = 'feed-relay-deployment-boundary'
    metadata = json.dumps({'main_module': 'index.mjs', 'compatibility_date': '2026-09-30'})
    data = (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n'
            f'Content-Type: application/json\r\n\r\n{metadata}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="index.mjs"; filename="index.mjs"\r\n'
            f'Content-Type: application/javascript+module\r\n\r\n').encode() + script.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
    call(prefix + '/scripts/' + NAME, 'PUT', data, 'multipart/form-data; boundary=' + boundary)
    call(prefix + '/scripts/' + NAME + '/subdomain', 'POST', b'{"enabled":true,"previews_enabled":false}')
    url = f'https://{NAME}.{subdomain}.workers.dev'
    Path('worker-url.txt').write_text(url + '\n')
    print('Deployment API succeeded. Live endpoint must still pass TECH-IL smoke test.')
    print(url)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(f'Worker deployed: {url}\n\nSet repository variable `TECH_IL_WORKER_URL` to this URL after the live smoke test succeeds.\n')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'url={url}\n')


if __name__ == '__main__':
    main()
