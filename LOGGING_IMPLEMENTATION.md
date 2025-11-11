# Logging Implementation Plan

## Overview
Implement structured logging system for spoo.me URL shortener with smart sampling for high-traffic endpoints (400k requests/day).

## Key Decisions
✅ **NO async logging** - Keep it simple, Vercel handles buffering  
✅ **Hash IPs in production** - Simple SHA-256 hash for GDPR compliance  
✅ **NO email logging** - Avoid PII entirely  
✅ **Smart sampling** - Reduce log volume for high-frequency events  
✅ **Structured JSON logs** - Easy parsing on Vercel/Sentry  
✅ **NO test files** - Focus on implementation and monitoring

---

## Dependencies

```bash
pip install structlog
```

Add to `requirements.txt`:
```
structlog==24.1.0
```

---

## Environment Variables

Add to `.env` and `.env.example`:
```bash
# Logging Configuration
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json                   # json (prod) or console (dev)

# Sampling Rates (0.0 to 1.0)
SAMPLE_RATE_REDIRECT=0.05        # 5% of URL redirects
SAMPLE_RATE_STATS=0.20           # 20% of stats queries
SAMPLE_RATE_CACHE=0.01           # 1% of cache operations
SAMPLE_RATE_EXPORT=0.80          # 80% of exports
```

---

## Task Breakdown

### **Task 1: Core Logging Infrastructure** ⭐ START HERE

**Files to create:**

#### `utils/logging_config.py` (~150 lines)
Core configuration module with:
- Environment-based log level setup
- Structured logging with `structlog`
- JSON formatter for production, console for development
- IP hashing function for production
- Sentry integration for ERROR+ levels
- Sampling rate configuration

#### `utils/logger.py` (~100 lines)
Logger factory with:
- `get_logger(name)` - Returns configured logger
- `should_sample(event_type)` - Sampling logic based on event type
- Context binding helpers
- IP anonymization wrapper

#### `utils/log_context.py` (~80 lines)
Flask request middleware:
- Generate unique `request_id` per request
- Attach user context (user_id, ip_hash, method, path)
- Auto-log request start/end with timing
- Bind context to all logs within request lifecycle

**Integration in `main.py`:**
```python
from utils.log_context import setup_logging_middleware

# After app initialization
setup_logging_middleware(app)
```

---

### **Task 2: Authentication & Authorization Logging**

**Files to update:** `blueprints/auth.py`, `blueprints/oauth.py`

**Replace print statements with:**

```python
from utils.logger import get_logger

log = get_logger(__name__)

# Login events
log.info("login_success", user_id=user_id, auth_method="password")
log.warning("login_failed", email_hash=hash_email(email), reason="invalid_credentials")

# Registration
log.info("user_registered", user_id=user_id, auth_method="password")

# Token refresh
log.info("token_refreshed", user_id=user_id)

# OAuth
log.info("oauth_login_success", user_id=user_id, provider="google")
log.error("oauth_callback_failed", provider="github", error=str(e))
log.info("oauth_account_linked", user_id=user_id, provider="discord")

# Permissions
log.warning("permission_denied", user_id=user_id, required_scope="urls:manage")
```

**What to log (100%):**
- Login success/failure + auth method
- Registration events
- Token refresh operations
- OAuth flow completion/errors
- Account linking events
- Permission denied (403s)

---

### **Task 3: URL Operations Logging**

**Files to update:** `blueprints/url_shortener.py`, `api/v1/shorten.py`, `api/v1/management.py`

```python
from utils.logger import get_logger

log = get_logger(__name__)

# URL creation
log.info("url_created", 
    alias=alias, 
    long_url=long_url, 
    owner_id=str(owner_id) if owner_id else None,
    schema="v2",
    has_password=bool(password),
    max_clicks=max_clicks
)

# URL updates
log.info("url_updated", 
    url_id=str(url_id), 
    owner_id=str(owner_id),
    fields_changed=list(updates.keys())
)

# URL deletion
log.info("url_deleted", url_id=str(url_id), alias=alias, owner_id=str(owner_id))

# Conflicts/Errors
log.warning("url_creation_failed", reason="alias_exists", alias=alias)
log.info("url_expired", url_id=str(url_id), reason="max_clicks_reached", total_clicks=total_clicks)
```

**What to log (100%):**
- URL creation (v1 & v2 schema)
- URL updates with changed fields
- URL deletions
- Alias conflicts
- Max clicks reached
- URL expiration events

---

### **Task 4: URL Redirector Logging (WITH SAMPLING)**

**Files to update:** `blueprints/redirector.py`

```python
from utils.logger import get_logger, should_sample

log = get_logger(__name__)

# Redirect events (5% sample)
if should_sample("url_redirect"):
    log.info("url_redirect",
        short_code=short_code,
        schema=schema_type,
        country=country,
        browser=browser,
        os=os_name,
        redirect_ms=redirect_ms,
        is_bot=is_bot
    )

# Bot blocking (100%)
log.info("bot_blocked", 
    short_code=short_code, 
    bot_name=bot_name, 
    user_agent=user_agent[:100]
)

# Errors (100%)
log.error("click_processing_failed",
    short_code=short_code,
    schema=schema_type,
    error=str(e),
    error_type=type(e).__name__
)

# URL not found (100%)
log.warning("url_not_found", short_code=short_code)

# Password protected access (100%)
log.info("password_required", short_code=short_code)
log.warning("password_incorrect", short_code=short_code)
```

**What to log:**
- URL redirects - **5% sample** (most frequent operation)
- Bot blocking events - **100%** (security)
- Click processing errors - **100%**
- URL not found - **100%**
- Password checks - **100%**

---

### **Task 5: Database Operations Logging**

**Files to update:** `utils/mongo_utils.py`

```python
from utils.logger import get_logger

log = get_logger(__name__)

# Connection events
log.info("mongodb_connected")
log.error("mongodb_connection_failed", error=str(e))

# Query errors
log.error("mongodb_query_failed",
    collection=collection_name,
    operation=operation,
    error=str(e)
)

# Schema validation warnings
log.warning("invalid_click_data", 
    reason="missing_meta_field",
    short_code=short_code
)

# Index creation
log.info("mongodb_indexes_created")
```

**What to log:**
- Database connection success/failure
- Query errors with collection + operation
- Schema validation warnings
- Index creation events

---

### **Task 6: Cache Operations Logging (WITH SAMPLING)**

**Files to update:** `cache/base_cache.py`, `cache/dual_cache.py`, `cache/cache_url.py`, `cache/cache_updates.py`

```python
from utils.logger import get_logger, should_sample

log = get_logger(__name__)

# Cache operations (1% sample)
if should_sample("cache_operation"):
    log.debug("cache_hit", key=key, cache_type="url")
    log.debug("cache_miss", key=key, cache_type="url")

# Cache errors (100%)
log.error("cache_error",
    operation="get",
    key=key,
    error=str(e),
    cache_type="redis"
)

# Cache refresh (100%)
log.error("cache_refresh_failed", 
    base_key=base_key, 
    error=str(e)
)

# Cache invalidation (100%)
log.info("cache_invalidated", 
    short_code=short_code,
    reason="url_updated"
)
```

**What to log:**
- Cache operations - **1% sample** (debug only)
- Cache errors - **100%**
- Cache refresh failures - **100%**
- Cache invalidation events - **100%**

---

### **Task 7: API Key & Rate Limiting Logging**

**Files to update:** `api/v1/keys.py`, `blueprints/limiter.py`

```python
from utils.logger import get_logger

log = get_logger(__name__)

# API key operations (100%)
log.info("api_key_created",
    user_id=str(user_id),
    key_prefix=token_prefix,
    scopes=scopes,
    expires_at=expires_at.isoformat() if expires_at else None
)

log.info("api_key_revoked",
    user_id=str(user_id),
    key_id=str(key_id),
    action="deleted" or "revoked"
)

log.warning("api_key_invalid",
    key_prefix=token[:8],
    reason="expired" or "revoked"
)

# Rate limiting (100%)
log.warning("rate_limit_hit",
    path=request.path,
    method=request.method,
    limit=limit_string,
    ip_hash=hash_ip(ip)
)
```

**What to log:**
- API key creation/revocation - **100%**
- Invalid API key usage - **100%**
- Rate limit hits - **100%** (potential abuse)

---

### **Task 8: Contact & Webhook Logging**

**Files to update:** `utils/contact_utils.py`, `blueprints/contact.py`

```python
from utils.logger import get_logger

log = get_logger(__name__)

# Contact form
log.info("contact_form_submitted", email_hash=hash_email(email))

# URL reports
log.info("url_reported", short_code=short_code, reason=reason)

# Webhook failures (100%)
log.error("webhook_failed",
    webhook_type="contact",
    error=str(e)
)

log.error("webhook_failed",
    webhook_type="url_report",
    short_code=short_code,
    error=str(e)
)

# hCaptcha
log.warning("captcha_failed", form_type="contact")
```

**What to log:**
- Contact form submissions - **100%**
- URL reports - **100%**
- Webhook failures - **100%**
- Captcha failures - **100%**

---

### **Task 9: Stats & Exports Logging (WITH SAMPLING)**

**Files to update:** `api/v1/stats.py`, `api/v1/exports.py`

```python
from utils.logger import get_logger, should_sample

log = get_logger(__name__)

# Stats queries (20% sample)
if should_sample("stats_query"):
    log.info("stats_query",
        scope=scope,
        group_by=group_by,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        filter_count=len(filters),
        duration_ms=duration
    )

# Export operations (80% sample)
if should_sample("stats_export"):
    log.info("stats_export",
        format=format,
        scope=scope,
        short_code=short_code if scope == "anon" else None,
        duration_ms=duration
    )

# Stats errors (100%)
log.error("stats_query_failed",
    scope=scope,
    error=str(e)
)
```

**What to log:**
- Stats queries - **20% sample**
- Export operations - **80% sample**
- Errors - **100%**

---

## What We Log (Summary)

### **Always Log (100%)**
- ✅ Authentication events (login, logout, registration)
- ✅ OAuth flows (success, failure, linking)
- ✅ URL operations (create, update, delete)
- ✅ API key operations (create, revoke, invalid usage)
- ✅ Rate limit hits
- ✅ All errors and exceptions
- ✅ Database connection issues
- ✅ Webhook failures
- ✅ Bot blocking events
- ✅ Cache errors and invalidations
- ✅ URL expiration events
- ✅ Permission denied (403s)

### **Sampled Logging**
- 🔸 URL redirects: **5%** (280k/day → 14k logged)
- 🔸 Stats queries: **20%** (40k/day → 8k logged)
- 🔸 Cache operations: **1%** (debug only)
- 🔸 Export operations: **80%**

### **Never Log**
- ❌ Full JWT tokens
- ❌ API key raw values (only prefix)
- ❌ Passwords (plain or hashed)
- ❌ Email addresses (never needed)
- ❌ Request/response bodies with PII

---

## Privacy & Security

### **IP Address Handling**
```python
# Production: Hash IPs with SHA-256
def hash_ip(ip: str) -> str:
    if os.getenv("ENV") == "production":
        return hashlib.sha256(ip.encode()).hexdigest()[:16]
    return ip  # Keep full IP in development
```

### **Sensitive Field Redaction**
```python
REDACTED_FIELDS = {
    'password', 'password_hash', 'token', 'api_key',
    'Authorization', 'Cookie', 'refresh_token', 'access_token'
}
```

### **GDPR Compliance**
- ✅ IP addresses hashed in production (irreversible)
- ✅ No email logging
- ✅ User IDs are non-PII (MongoDB ObjectIds)
- ✅ Auto-delete logs >30 days (Vercel default)
- ✅ Country-level geolocation only (not city in logs)

---

## Log Volume Estimation

### **Current Traffic: 400,000 requests/day**

**Breakdown:**
- Redirects (70%): 280,000/day × 5% = **14,000 logs**
- Stats queries (10%): 40,000/day × 20% = **8,000 logs**
- URL creation (5%): 20,000/day × 100% = **20,000 logs**
- Auth events (3%): 12,000/day × 100% = **12,000 logs**
- Errors (1%): 4,000/day × 100% = **4,000 logs**
- Other (11%): 44,000/day × 30% = **13,200 logs**

**Total: ~71,200 logs/day**

**Data Volume:**
- Average log size: ~300 bytes JSON
- Daily: 71,200 × 300 bytes = **21.4 MB/day**
- Monthly: 21.4 MB × 30 = **642 MB/month**

✅ Well within Vercel limits

---

## Performance Impact

### **Without Sampling**
- Per-request overhead: ~2-4ms
- CPU impact: ~1-2%
- ❌ Not acceptable for 400k req/day

### **With Smart Sampling (Recommended)**
- Average overhead: **~0.3ms per request**
- 95th percentile: **~1ms**
- CPU impact: **<0.5%**
- ✅ Negligible impact

**Current avg redirect time:** 142ms  
**With logging:** ~142.3ms (+0.2%)  
✅ **Acceptable**

---

## Implementation Order

### **Phase 1: Foundation (Day 1)** - 3-4 hours
1. ✅ Create `utils/logging_config.py`
2. ✅ Create `utils/logger.py`
3. ✅ Create `utils/log_context.py`
4. ✅ Update `requirements.txt`
5. ✅ Update `.env.example`
6. ✅ Register middleware in `main.py`
7. ✅ Test in development

### **Phase 2: Critical Paths (Day 2-3)** - 6-8 hours
8. ✅ Task 2: Auth & OAuth logging
9. ✅ Task 3: URL operations logging
10. ✅ Task 5: Database logging
11. ✅ Task 7: API keys & rate limiting
12. ✅ Deploy to staging, monitor

### **Phase 3: High-Volume Paths (Day 4-5)** - 4-5 hours
13. ✅ Task 4: Redirector logging (with sampling)
14. ✅ Task 6: Cache logging (with sampling)
15. ✅ Task 8: Contact & webhooks
16. ✅ Monitor performance impact

### **Phase 4: Polish (Day 6-7)** - 2-3 hours
17. ✅ Task 9: Stats & exports (with sampling)
18. ✅ Fine-tune sampling rates based on data
19. ✅ Update documentation
20. ✅ Deploy to production with monitoring

**Total effort: 16-20 hours (2-3 focused days)**

---

## Monitoring & Iteration

### **Week 1: Watch These Metrics**
- Log volume (should be ~70k/day)
- Performance impact (p95 latency)
- Sentry error rate
- Vercel log storage usage

### **Week 2: Optimize**
- Adjust sampling rates if needed
- Add/remove log points based on value
- Fine-tune log levels

### **Month 1: Review**
- Identify most valuable logs
- Remove noisy/low-value logs
- Document common debugging patterns

---

## Quick Reference

### **Get a logger**
```python
from utils.logger import get_logger

log = get_logger(__name__)
```

### **Log with context**
```python
log.info("event_name", key1="value1", key2="value2")
log.warning("warning_event", user_id=user_id, reason="invalid_input")
log.error("error_event", error=str(e), error_type=type(e).__name__)
```

### **Sample high-frequency events**
```python
from utils.logger import should_sample

if should_sample("url_redirect"):
    log.info("url_redirect", short_code=short_code)
```

### **Hash IPs in production**
```python
from utils.logger import hash_ip

log.warning("suspicious_activity", ip_hash=hash_ip(client_ip))
```

---

## Files to Create

```
utils/
  ├── logging_config.py      (~150 lines) - Core configuration
  ├── logger.py              (~100 lines) - Logger factory with sampling
  └── log_context.py         (~80 lines)  - Request middleware
```

## Files to Update

```
main.py                      (5 lines)     - Register middleware
requirements.txt             (1 line)      - Add structlog
.env.example                 (6 lines)     - Logging config

blueprints/
  ├── auth.py                (~15 spots)   - Replace print()
  ├── oauth.py               (~10 spots)
  ├── redirector.py          (~8 spots)
  ├── url_shortener.py       (~5 spots)
  └── contact.py             (~3 spots)

api/v1/
  ├── shorten.py             (~5 spots)
  ├── management.py          (~8 spots)
  ├── keys.py                (~5 spots)
  ├── stats.py               (~3 spots)
  └── exports.py             (~3 spots)

utils/
  ├── mongo_utils.py         (~10 spots)
  └── contact_utils.py       (~3 spots)

cache/
  ├── base_cache.py          (~3 spots)
  ├── dual_cache.py          (~2 spots)
  ├── cache_url.py           (~3 spots)
  └── cache_updates.py       (~2 spots)
```

---

## Notes

- No async logging needed (sync Flask app, Vercel handles buffering)
- No test files needed (focus on monitoring in production)
- IP hashing (not rotation) - simple SHA-256
- No email logging to avoid PII
- Sentry auto-captures ERROR+ logs
- JSON logs in production, pretty console in dev
- Sampling configurable via environment variables
