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
