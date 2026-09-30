import test from 'node:test';
import assert from 'node:assert/strict';
import worker, {allowedTarget} from './index.mjs';
const posts = 'https://tech-il.co.il/wp-json/wp/v2/posts?per_page=25&orderby=date&order=desc&_fields=id%2Cdate_gmt%2Clink%2Ctitle%2Cexcerpt';
test('only canonical public listings and robots are accepted', () => {
  assert.equal(allowedTarget(posts), posts);
  assert.equal(allowedTarget('https://tech-il.co.il/robots.txt'), 'https://tech-il.co.il/robots.txt');
  for (const bad of [null, 'bad', 'https://evil.test/robots.txt', 'http://tech-il.co.il/robots.txt',
    'https://user:pass@tech-il.co.il/robots.txt', 'https://tech-il.co.il/robots.txt#x',
    posts + '&extra=1', posts + '&per_page=25', posts.replace('per_page=25', 'per_page=100'),
    'https://tech-il.co.il/wp-admin', 'https://tech-il.co.il/wp-json/wp/v2/posts']) {
    assert.equal(allowedTarget(bad), null, String(bad));
  }
});
test('rejects writes and arbitrary targets without fetching', async () => {
  assert.equal((await worker.fetch(new Request('https://relay.test/', {method: 'POST'}))).status, 405);
  assert.equal((await worker.fetch(new Request('https://relay.test/?url=https://evil.test/'))).status, 400);
});
test('forwards public JSON, caches, strips cookies, never follows redirects', async () => {
  const oldFetch = globalThis.fetch;
  globalThis.caches = {default: {match: async () => null, put: async () => {}}};
  globalThis.fetch = async (url, options) => {
    assert.equal(url, posts); assert.equal(options.redirect, 'manual');
    assert.equal(options.headers.Cookie, undefined);
    return new Response('[]', {headers: {'content-type': 'application/json', 'set-cookie': 'private'}});
  };
  try {
    const pending = [];
    const r = await worker.fetch(new Request('https://relay.test/?url=' + encodeURIComponent(posts)), {}, {waitUntil: p => pending.push(p)});
    assert.equal(r.status, 200); assert.equal(r.headers.get('set-cookie'), null);
    assert.equal(await r.text(), '[]'); await Promise.all(pending);
  } finally { globalThis.fetch = oldFetch; }
});
test('rejects non-JSON and redirects from upstream', async () => {
  const oldFetch = globalThis.fetch;
  globalThis.caches = {default: {match: async () => null}};
  try {
    for (const response of [new Response('<html>', {headers: {'content-type': 'text/html'}}), new Response('', {status: 302})]) {
      globalThis.fetch = async () => response;
      const r = await worker.fetch(new Request('https://relay.test/?url=' + encodeURIComponent(posts)));
      assert.equal(r.status, 502);
    }
  } finally { globalThis.fetch = oldFetch; }
});
