# k6 Performance Tests

Performance test suite for spoo.me URL shortener using [k6](https://k6.io/).

## Prerequisites

- [k6](https://k6.io/docs/get-started/installation/) installed
- Application running locally (`uvicorn` or `docker compose up`)

## Test Types

| Type | Purpose | VUs | Duration |
|------|---------|-----|----------|
| **Smoke** | Sanity check — app works under minimal load | 1-5 | 30s |
| **Load** | Sustained traffic — normal production patterns | 100-500 | 10m |
| **Stress** | Push to breaking point — find capacity limits | Ramp to 1000+ | 15m |
| **Spike** | Sudden traffic burst — test recovery | Normal → 5x → Normal | 10m |
| **Soak** | Long-running — detect memory leaks, degradation | 50 | 30m |

## Quick Start

```bash
# Smoke test (quick sanity check)
k6 run tests/k6/scenarios/redirect-smoke.js

# Load test
k6 run tests/k6/scenarios/redirect-load.js

# Against a remote server
K6_BASE_URL=https://staging.spoo.me k6 run tests/k6/scenarios/redirect-smoke.js
```

## Scenarios

### Redirect Tests
The hot path — `GET /{short_code}` at ~400k req/day in production.

- `redirect-smoke.js` — 5 VUs, 30s
- `redirect-load.js` — 200 VUs, 10m sustained
- `redirect-stress.js` — Ramp to 1000 VUs, find breaking point
- `redirect-spike.js` — 50 → 500 → 50 VUs, test recovery
- `redirect-soak.js` — 50 VUs, 30m, detect degradation

### API v1 Tests
JSON API endpoints (`/api/v1/*`).

- `api-smoke.js` — All API endpoints, 2 VUs, 30s
- `api-load.js` — Shorten + stats + management, 50 VUs, 5m

### Auth Tests
Authentication endpoints (`/auth/*`).

- `auth-smoke.js` — Login, register, refresh, 2 VUs, 30s

### Legacy Tests
Legacy v1 endpoints (`POST /`, `/emoji`, `/metric`).

- `legacy-smoke.js` — All legacy endpoints, 2 VUs, 30s
- `legacy-load.js` — Metric + redirect mix, 100 VUs, 5m

### Mixed Realistic
Weighted traffic simulation matching production patterns.

- `mixed-realistic.js` — 60min with realistic traffic distribution

## Test Data

Tests auto-create URLs in k6's `setup()` function — no manual setup needed. URLs are created via the API using `https://httpstat.us/200` as the target (lightweight mock).

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `K6_BASE_URL` | `http://localhost:8000` | Base URL of the app |

## Thresholds

All tests include pass/fail thresholds:
- **Smoke**: p95 < 500ms, error rate < 1%
- **Load**: p95 < 2s, error rate < 1%
- **Stress**: p95 < 5s, error rate < 5%
- **Spike**: p95 < 3s, error rate < 5%
- **Soak**: p95 < 2s, error rate < 1%

## Architecture

```
tests/k6/
├── lib/
│   ├── config.js    # BASE_URL, thresholds
│   ├── data.js      # User agents, IPs, referrers (SharedArray)
│   └── helpers.js   # Header builders, check helpers
├── setup.js         # Auto URL creation for tests
├── scenarios/       # All test scripts
└── README.md
```

## Results

### api-load.js

| Window | VU ramp | Requests/s | p50 | p95 | p99 | HTTP failures |
|---|---:|---:|---:|---:|---:|---:|
| 0:00-1:00 | 0-50 | 12.97 | 2.57 ms | 6.45 ms | 9.10 ms | 39.46% |
| 1:00-4:00 | 50-150 | 49.87 | 2.44 ms | 6.93 ms | 10.67 ms | 38.98% |
| 4:00-7:00 | 150-300 | 111.66 | 3.42 ms | 18.76 ms | 115.04 ms | 39.64% |
| 7:00-10:00 | 300-500 | 197.09 | 6.74 ms | 128.68 ms | 316.98 ms | 39.76% |
| 10:00-13:00 | 500-800 | 279.29 | 30.87 ms | 1.70 s | 3.10 s | 40.20% |
| 13:00-16:00 | 800-1,200 | 268.57 | 1.07 s | 5.00 s | 6.18 s | 40.05% |
| 16:00-19:00 | 1,200-1,600 | 215.93 | 2.59 s | 13.82 s | 17.44 s | 40.59% |
| Overall | 0-1,600-0 | 180.65 | 246.28 ms | 6.90 s | 13.05 s | 39.90% |
| Status breakdown | HTTP 201 | 87,022 | | | | Shorten |
| Status breakdown | HTTP 200 | 43,542 | | | | Health |
| Status breakdown | HTTP 401 | 86,715 | | | | Stats 65,007; export 21,708 |

Run on 2026-10-20 at commit `16ead788e02b81cc43e18bd59431145834a074a8` with k6 v2.3.0; the app, MongoDB, Redis, and k6 shared one 4 vCPU, 8 GB machine. Rate limits were raised locally to `1000000 per minute`, Redis was flushed, and all requests came from one IP; the earlier default-limit run rejected 78.18% of traffic at 50 VUs. Latency degraded consistently around 700-750 VUs, where p95 reached 3.22 s at 238.6 req/s after a healthy 650-700 VU window at 316.5 req/s, 609 ms p95, and 1.81 s p99. The single uvicorn app process reached about one CPU core while MongoDB stayed near 12%, Redis near 1%, k6 near 18%, and the host retained about 65% idle CPU, indicating single-process app saturation rather than host, MongoDB, Redis, or k6 exhaustion. No 429 or 5xx responses occurred, but stats and export returned 401 throughout because the scenario sends no credentials, so the 1% error threshold is not a usable capacity signal for this script.

### redirect-load.js

| Metric | Result |
|---|---:|
| Date | 2026-10-20 |
| Git commit tested | `16ead788e02b81cc43e18bd59431145834a074a8` |
| Machine | 4 vCPU (Ryzen 9 9950X), 8 GB RAM; app, MongoDB 9.0.4, Redis 8.10.2 and k6 on one box |
| App | Python 3.14, one `uvicorn app.main:app --no-access-log` worker, clicks tracked inline |
| k6 version | v2.3.0 |
| Total requests | 128,468 |
| Requests/s | 93.01 |
| `http_req_duration` avg | 7.65 ms |
| `http_req_duration` p50 | 5.02 ms |
| `http_req_duration` p90 | 11.00 ms |
| `http_req_duration` p95 | 15.18 ms |
| `http_req_duration` p99 | 59.52 ms |
| `http_req_duration` max | 306.81 ms |
| `http_req_failed` | 0.00% (0 / 128,468) |
| Check: setup URLs created | 100% (14 / 14) |
| Check: is redirect (301/302) | 100% (128,454 / 128,454) |
| Check: has Location header | 100% (128,454 / 128,454) |
| Check: response time < 2s | 100% (128,454 / 128,454) |
| Threshold `p(95)<2000` | Pass |
| Threshold `p(99)<5000` | Pass |
| Threshold `http_req_failed rate<0.01` | Pass |

Requests/s is set by the scenario's 1 to 3 s sleep, not by the app: the uvicorn worker used about 20 to 25% of one core during the hold. Latency includes contention because everything ran on one machine. No rate limit was changed, since `GET /{alias}` is exempt and setup()'s 9 API and 5 legacy creates fit under the anonymous limits.

### Past the limit

| Run | Requests | Req/s | p50 | p95 | Max | Failed | Thresholds |
|---|---:|---:|---:|---:|---:|---:|---|
| `redirect-stress.js` as written, 0 to 1,500 VUs | 359,329 | 239.4 | 1.91 s | 6.60 s | 9.45 s | 0.00% | p95 fail, errors pass |
| `redirect-stress.js` with `--stage` up to 10,000 VUs, then 2 min at 50 | 140,539 | 173.4 | 23.41 s | 60 s | 60 s | 15.31% | both fail |
| `redirect-load.js` at 200 VUs for 8 min, Redis stopped 60 s, then MongoDB stopped 60 s | 40,660 | 79.4 | 6.02 ms | 34.55 ms | 30.7 s | 0.06% | all pass |

Throughput peaked at about 320 req/s between 300 and 450 VUs, then fell to 200 to 240 req/s as VUs kept rising. From about 480 VUs the uvicorn worker sat at 100% of one core while the host stayed about 60% idle, so one Python process is the limit, not the machine, MongoDB or Redis.

Requests started failing at roughly 8,500 VUs, all on the client side: 12,167 got no response within k6's 60 s timeout, 4,960 were never accepted and 4,401 were reset, with 147,041 listen queue overflows in the kernel. No response was a 5xx and the process never restarted. Failures stopped 26 s after load dropped to 50 VUs, and a smoke run right after had a p95 of 13.9 ms. App memory grew from 250 MB to 1.4 GB at 10,000 open connections and stayed at 1.2 GB afterwards.

With Redis stopped, no request failed: the app logged cache errors and read from MongoDB. With MongoDB stopped, redirects kept working from the Redis cache, but clicks in that minute were dropped (`click_tracking_failed`, no retry). The two legacy `/emoji` aliases, which are never cached, waited 30 s for server selection and returned 500, which accounts for all 27 failures.

### Spike: shorten, auth, rate limiter, stats

Run on 2026-10-21 at commit `16ead788e02b81cc43e18bd59431145834a074a8` with k6 v2.3.0 on an 8 vCPU, 16 GB box. The app ran like production: `uvicorn app.main:app --workers 2 --timeout-keep-alive 5`, the click worker, `CLICK_EVENTS_SINK=stream` with a separate queue Redis, `SAFETY_ENABLED=true` (no Web Risk key), `ENV=production`, JSON logs. Both uvicorn workers, the click worker and both Redis containers were pinned to 2 cores (a CCX13 has 2 vCPU), mongod to 2 more, and k6 to the last 4. Python 3.14.6, MongoDB 9.0.4, Redis 8.10.2 (cache capped at 512 MB, `allkeys-lru`).

No rate limit was changed; there is no env setting for them. Spike traffic came from distinct `CF-Connecting-IP` values, one seeded API key or session per VU, so the limiter did not hide the backend. Data: 500 users with API keys, and an owner with 40 links and 2M clicks over 89 days inside a 7.5M click collection.

| Run | Peak | Throughput at peak | p95 at peak | Failures | Recovery |
|---|---:|---:|---:|---|---|
| Shorten, anonymous, 5 to 500 VUs in 10 s | 500 | 64 creates/s | 8.6 s | none | normal latency as soon as the queue drained |
| Shorten, API key, 5 to 500 VUs in 10 s | 500 | 36 creates/s | 17.2 s | none | same |
| Shorten, anonymous, 5 to 2,000 VUs | 2,000 | 40 creates/s | 60 s | 33% k6 timeouts | same |
| Same custom alias from 50 clients at once, 20 rounds | 50 | | 951 ms | 57 of 1,000 were 500 | |
| Login, 0 to 300 VUs in 5 s, 100 redirect VUs alongside | 300 | 7.4 logins/s | 60 s | 52 login timeouts | |
| Register, 0 to 300 VUs in 5 s, same redirect load | 300 | 7.0 registers/s | 60 s | 36 timeouts | |
| Redirects during the login spike | 100 | 5.8 req/s (51 before) | 21.8 s (36 ms before) | none | 18 to 31 ms once logins drained |
| One IP, then one API key, 200 VUs, Redis up | 200 | | | 20 and 60 created, exactly the limits | |
| Same, Redis stopped for 20 s | 200 | | | 4,360 HTTP 500 | |
| Same, Redis paused for 20 s | 200 | | | both workers served nothing for 20 s, `/health` included | |
| Stats and export, 0 to 200 VUs, one owner | 200 | 3.4 req/s | 60 s | 37.5% timeouts | none within 60 s |

Where it broke and why:

- Shorten is CPU bound at about 64 creates/s on 2 cores. Profiles put 16% of worker time in argon2 for the 10% of creates that set a password, 15% in the rate limiter's synchronous Redis calls (hit, then get and ttl for the headers, all blocking the event loop), and about 9% in the URL safety gate (pattern, verdict and feed lookups plus the L1 counters). The safety checks never blocked or queued a create, and L1 fired once per domain and window as designed. No duplicate aliases: the unique index held. Past about 1,000 VUs requests sit in the event loop until k6 gives up at 60 s, and the server still finishes them: 625 links were created for clients that had already timed out. Worker RSS stayed between 230 and 340 MB.
- Login and register are argon2 bound at about 7.5 per second for the box, and argon2 ran on the event loop, so every redirect on a worker waited behind the queued logins.
- With Redis up the limiter is exact across two workers. When Redis is stopped every limited route returns 500 after redis-py's retry backoff, and when it hangs the synchronous client blocks both workers. Separately, any made-up `Authorization` header or `access_token` cookie got its own bucket: from one IP, 477 wrong-password logins went through in 40 s (limit 5 per minute) and 245 anonymous links were created (limit 20 per minute).
- Stats and export break in MongoDB. One 90-day account query for the 2M-click owner takes 9.4 s alone, 26.7 s with every group-by, because each request runs a `$facet` with `$addToSet` over every IP for unique counts. At 200 VUs mongod grew to 12.9 GB and was OOM-killed. Abandoned aggregations kept running after k6 timed out (no `maxTimeMS`), pymongo retried them against the restarted mongod, and it was OOM-killed a second time after the test ended. During the outage the stats endpoint answered 200 with `total_clicks: 0`.

Slowest profiled queries, all on `clicks`:

| ms | Shape | Plan |
|---:|---|---|
| 26,599 | owner, 90 days, `$facet` over 8 group-bys with `$addToSet` | `CLUSTERED_IXSCAN`, all buckets in range |
| 9,416 | owner, 90 days, summary and time | same |
| 6,758 | owner export, 90 days, summary and time | same |
| 1,767 | one link, 90 days | `meta.url_id` index, 467 buckets |

For this owner (26% of all clicks) the planner scans every bucket in the window (572,837) instead of the owner's 7,416; hinting `meta.owner_id_1_clicked_at_-1` cuts the match from 546 ms to 73 ms, but `$addToSet` dominates either way. Owners with ordinary volumes get the owner index.

Fixes are in this branch, one commit each with a test, with before and after numbers from the same k6 slice:

| Commit | Slice | Before | After |
|---|---|---|---|
| `fix(shorten): return 409 when a custom alias is taken mid-request` | alias race | 57 HTTP 500 | 0 HTTP 500, 980 HTTP 409 |
| `fix(auth): run argon2 hashing off the event loop` | redirect p95 during the login spike | 21.8 s at 5.8 req/s | 102 ms at 49.3 req/s |
| `fix(rate-limit): give a token its own bucket only once verified` | one IP, random bearer per request | 477 logins, 245 creates | 5 logins, 20 creates |
| `fix(rate-limit): fall back to memory when Redis is down or wedged` | Redis stopped, then paused | 4,360 HTTP 500; 20 s freeze | 0 HTTP 500, no freeze; 40 creates, the limit once per worker |
| `fix(cache): time out cache Redis calls instead of hanging redirects` | redirects only, Redis paused 20 s | 50 served, rest hung 20 s | 630 served at 1.05 s p50 from MongoDB |
| `fix(stats): fail the request when the click aggregation fails` | owner stats, MongoDB stopped 30 s | 7 HTTP 200 with 0 clicks | 0; 10 HTTP 500 |

The stats OOM has no fix here: it needs bounded concurrency or precomputed counts, not a patch.

Script fixes in this change: `auth-smoke.js` used `.invalid` addresses, which fail email validation, so login, register and password reset only ever measured 422 (70% failure rate in a 30 s run); it now uses `example.com` and accepts 429 once a per-IP auth limit is spent. `api-load.js` sent stats and export with no credentials, which only measured 401; set `K6_API_KEY` to include them.

Caveat: one box. MongoDB had 2 dedicated cores and no memory cap, unlike a hosted cluster, and k6 shared the machine's memory and network stack. The spike scripts and seed data were scratch and are not committed.
