# TECH-IL public feed relay

This is not an open proxy. GET requests can fetch only TECH-IL's public robots.txt
or the fixed WordPress listing (25 posts, title/link/date/excerpt fields).
No inbound cookies, Authorization headers or arbitrary upstream headers are forwarded.
Redirects, other hosts, admin endpoints and write methods are rejected.
Successful responses are cached for 15 minutes to reduce publisher traffic and quota use.
Upstream errors are not cached. TECH-IL robots rules are still checked by the generator.

## One-time setup (phone browser is enough)

1. Sign into a free Cloudflare account. In Workers & Pages, set up the free
   workers.dev subdomain if none exists. No custom domain or paid plan is needed.
2. Create a custom API token with Account > Workers Scripts > Edit, scoped to
   this account. The Account ID is available in the account dashboard.
   No Zone permissions or global API key are needed.
3. In this GitHub repository's Settings > Secrets and variables > Actions,
   add the token as secret `CLOUDFLARE_API_TOKEN` and the account ID as variable
   `CLOUDFLARE_ACCOUNT_ID`. Never put the token in source code, chat or logs.
4. Run Actions > Deploy TECH-IL relay > Run workflow. It uploads the script,
   enables its workers.dev route and runs a live TECH-IL generation smoke test
   from the GitHub runner. Do not call the deployment finished if this test fails.
5. After the test succeeds, set repository variable `TECH_IL_WORKER_URL` to the
   exact URL in the successful run summary. Run Generate feeds to publish a
   fresh TECH-IL feed, then check status.json and feeds/tech-il.xml.

Only TECH-IL is relayed. If the URL is unset, the old direct fetch remains.
Existing published feed files survive temporary failures, as before.
A changed egress IP is not a guarantee: TECH-IL could block Workers too.
Deployment never enables a paid plan. The free plan has 100,000 requests/day;
48 scheduled generator runs/day normally need 144 TECH-IL requests (robots
checks twice plus one listing). Cache hits reduce upstream fetches.
The narrow public endpoint has no secret key; unrelated targets cannot spend
quota on arbitrary proxy traffic, but public callers could still exhaust the
free daily request quota. Add Cloudflare Access if that becomes a problem.

## Local tests

    node --test worker/index.test.mjs
    python3 -m unittest discover -s tests -p 'test_*.py'

Sources:
- https://developers.cloudflare.com/api/resources/workers/subresources/scripts/methods/update/
- https://developers.cloudflare.com/api/resources/workers/subresources/subdomains/methods/get/
- https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/subdomain/
- https://developers.cloudflare.com/fundamentals/api/get-started/create-token/
- https://developers.cloudflare.com/workers/platform/limits/
