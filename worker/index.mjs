// A read-only relay for two public TECH-IL endpoints, never a general proxy.
const POSTS = 'https://tech-il.co.il/wp-json/wp/v2/posts?per_page=25&orderby=date&order=desc&_fields=id%2Cdate_gmt%2Clink%2Ctitle%2Cexcerpt';
const ROBOTS = 'https://tech-il.co.il/robots.txt';
const UA = 'israeli-no-rss-feeds (+https://github.com/yohaybn/israeli-no-rss-feeds)';

export function allowedTarget(value) {
  try {
    const url = new URL(value);
    if (url.username || url.password || url.hash || url.origin !== 'https://tech-il.co.il') return null;
    if (url.pathname === '/robots.txt' && !url.search) return ROBOTS;
    if (url.pathname !== '/wp-json/wp/v2/posts') return null;
    const required = new URL(POSTS).searchParams;
    if ([...url.searchParams].length !== [...required].length) return null;
    for (const [key, val] of required) if (url.searchParams.get(key) !== val) return null;
    return POSTS;
  } catch { return null; }
}

export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'GET') return new Response('GET only', { status: 405 });
    const target = allowedTarget(new URL(request.url).searchParams.get('url'));
    if (!target) return new Response('Target not allowed', { status: 400 });
    const key = new Request(new URL('/?url=' + encodeURIComponent(target), request.url));
    const cached = await caches.default.match(key);
    if (cached) return cached;
    try {
      const upstream = await fetch(target, {
        headers: { 'User-Agent': UA, 'Accept': target === POSTS ? 'application/json' : 'text/plain' },
        redirect: 'manual', signal: AbortSignal.timeout(20000)
      });
      if (!upstream.ok) return new Response('Upstream unavailable', { status: 502 });
      const type = upstream.headers.get('content-type') || '';
      if (target === POSTS && !type.toLowerCase().includes('application/json')) {
        return new Response('Upstream did not return JSON', { status: 502 });
      }
      const response = new Response(upstream.body, {
        headers: { 'Content-Type': type || 'text/plain', 'Cache-Control': 'public, max-age=900',
          'X-Content-Type-Options': 'nosniff' }
      });
      ctx.waitUntil(caches.default.put(key, response.clone()));
      return response;
    } catch { return new Response('Upstream unavailable', { status: 502 }); }
  }
};
