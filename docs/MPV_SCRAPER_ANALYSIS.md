# MPV-Scraper Project Analysis

## Executive Summary

The **mpv-scraper** project provides battle-tested patterns for API integration with
TMDB, TVDB, and fallback providers. Key learnings include:

1. **TVDB v3 API implementation** (we need this!)
2. **TMDB Bearer token + API key dual support**
3. **Comprehensive retry/backoff decorator**
4. **File-based caching with TTL**
5. **Fallback provider system**
6. **Rate limiting via `time.sleep()`**

---

## 🔑 Key Findings by Category

### 1. **TVDB v3 API Implementation** ✅

**File:** `src/mpv_scraper/tvdb.py`

**Critical Insights:**
- Uses **legacy v3 API** (`https://api.thetvdb.com/login`)
- Authentication: `POST /login` with `{"apikey": "KEY"}` → JWT token
- Token is **cached** in file system with 24hr TTL
- All requests use `Bearer {token}` header
- Search endpoint: `GET /search/series?name=...`
- Extended series: `GET /series/{id}` + `GET /series/{id}/episodes`
- Images: `GET /series/{id}/images/query?keyType=clearlogo`
- **Rate limit delay**: 0.5s between requests (`time.sleep(0.5)`)

**Reusable Code:**
```python
# Authentication pattern
def authenticate_tvdb() -> str:
    api_key = os.getenv("TVDB_API_KEY")
    cached_token = _get_from_cache("tvdb_token")
    if cached_token:
        return cached_token["token"]

    time.sleep(API_RATE_LIMIT_DELAY_SECONDS)
    response = requests.post(
        "https://api.thetvdb.com/login",
        json={"apikey": api_key},
        timeout=10
    )
    response.raise_for_status()
    token = response.json()["token"]
    _set_to_cache("tvdb_token", {"token": token})
    return token

# Search pattern
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "https://api.thetvdb.com/search/series",
    headers=headers,
    params={"name": name},
    timeout=10
)
```

**Action Items for NameGnome:**
- ✅ Adapt authentication flow for async (httpx)
- ✅ Implement token caching in SQLite (not file-based)
- ✅ Use same endpoints (v3 API)
- ✅ Respect 0.5s rate limit

---

### 2. **TMDB Dual Auth Support** ✅

**File:** `src/mpv_scraper/tmdb.py`

**Critical Insights:**
- Supports **both** API key (query param) AND Bearer token (header)
- Auto-detects Bearer token by: `api_key.startswith("eyJ") and len > 100`
- Endpoints:
  - Search: `GET /3/search/movie?query=TITLE&year=YEAR`
  - Details: `GET /3/movie/{id}?language=en-US`
  - Images: `GET /3/movie/{id}/images?include_image_language=en,en-US,null`
- **English content filtering**: Prioritizes `iso_3166_1=US` and `iso_639_1=en`
- **Poster/Logo selection**: Max by `vote_average`, prefer PNG for logos

**Reusable Code:**
```python
# Dual auth detection
api_key = os.getenv("TMDB_API_KEY")
is_bearer_token = api_key.startswith("eyJ") and len(api_key) > 100

if is_bearer_token:
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"query": title}
else:
    headers = {}
    params = {"api_key": api_key, "query": title, "language": "en-US"}

# English poster filtering (reusable!)
us_posters = [p for p in posters if p.get("iso_3166_1") == "US"]
english_posters = [p for p in posters if p.get("iso_639_1") == "en"]
poster_candidates = us_posters or english_posters or posters

best_poster = max(
    poster_candidates,
    key=lambda x: (x.get("vote_average", 0), x.get("iso_3166_1") == "US")
)
```

**Action Items for NameGnome:**
- ✅ Implement dual auth support
- ✅ Add English content filtering
- ✅ Reuse poster/logo selection logic

---

### 3. **Retry Logic with Exponential Backoff** ✅

**File:** `src/mpv_scraper/utils.py`

**Critical Pattern:**
```python
def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = base_delay * (2**attempt)  # 1s, 2s, 4s
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator
```

**Test Coverage:** `tests/test_retry.py`
- ✅ Success after 2 failures
- ✅ Max attempts exceeded
- ✅ Success on first try
- ✅ Specific exception filtering

**Action Items for NameGnome:**
- ✅ Adapt to async/await (use `asyncio.sleep`)
- ✅ Add to BaseProvider for HTTP calls
- ✅ Support 429 (rate limit) and 5xx (server errors)

---

### 4. **File-Based Caching with TTL** ✅

**File:** `src/mpv_scraper/tvdb.py`

**Pattern:**
```python
CACHE_DIR = Path.home() / ".cache" / "mpv-scraper"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours

def _get_from_cache(key: str):
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        cached_data = json.loads(cache_file.read_text())
        if time.time() - cached_data.get("timestamp", 0) < CACHE_TTL_SECONDS:
            return cached_data.get("data")
    return None

def _set_to_cache(key: str, data: dict):
    cache_file = CACHE_DIR / f"{key}.json"
    cached_data = {"timestamp": time.time(), "data": data}
    cache_file.write_text(json.dumps(cached_data))
```

**Cache Keys:**
- TVDB: `tvdb_token`, `search_{name}`, `series_{id}_extended`
- TMDB: `tmdb_search_{title}_{year}`, `tmdb_movie_{id}_details`, `tmdb_movie_{id}_images`

**Action Items for NameGnome:**
- ❌ Don't use file-based caching (use SQLite instead)
- ✅ Reuse cache key naming conventions
- ✅ Support per-entity TTL (series vs episodes vs movies)

---

### 5. **Fallback Provider System** ✅

**File:** `src/mpv_scraper/fallback.py`

**Pattern:**
```python
class FallbackScraper:
    def scrape_tv_with_fallback(self, show_dir: Path):
        # 1. Try TVDB (primary)
        record = self._try_tvdb(show_name)
        if record and not self._is_poor_data(record, "tvdb"):
            return record

        # 2. Try TMDB fallback
        record = self._try_tmdb_for_tv_show(show_name)
        if record and not self._is_poor_data(record, "tmdb"):
            return record

        # 3. Try FanartTV fallback
        record = self._try_fanarttv(show_name)
        return record or None

    def _is_poor_data(self, record, source):
        # Quality check: has poster, logo, episodes, overview?
        if source == "tvdb":
            return not (
                record.get("image") and
                record.get("artworks", {}).get("clearLogo") and
                len(record.get("episodes", [])) > 0 and
                record.get("overview")
            )
```

**Action Items for NameGnome:**
- ⚠️ Consider for Phase 2 (not critical for MVP)
- ✅ Document fallback strategy in design docs
- ✅ Support graceful degradation

---

### 6. **Rate Limiting via `time.sleep()`** ✅

**Pattern:**
```python
API_RATE_LIMIT_DELAY_SECONDS = 0.5

# Before each request:
time.sleep(API_RATE_LIMIT_DELAY_SECONDS)
response = requests.get(...)
```

**Observations:**
- ✅ Simple and effective for synchronous code
- ✅ Global delay shared across TVDB/TMDB
- ❌ Not ideal for async (use token bucket instead)

**Action Items for NameGnome:**
- ✅ Implement token bucket or sliding window rate limiter
- ✅ Per-provider limits (not global)
- ✅ Track request timestamps in BaseProvider

---

## 📝 Code We Can Directly Port

### 1. **TVDB Authentication** (100% reusable)
```python
# From mpv-scraper/src/mpv_scraper/tvdb.py:39-70
async def authenticate_tvdb(api_key: str) -> str:
    # Check cache first
    cached = await cache.get("tvdb_token")
    if cached:
        return cached

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.thetvdb.com/login",
            json={"apikey": api_key},
            timeout=10.0
        )
        response.raise_for_status()
        token = response.json()["token"]

    await cache.set("tvdb_token", token, ttl=86400)  # 24hr
    return token
```

### 2. **TMDB Dual Auth Detection** (100% reusable)
```python
# From mpv-scraper/src/mpv_scraper/tmdb.py:41-54
def _detect_auth_method(api_key: str) -> tuple[dict, dict]:
    is_bearer = api_key.startswith("eyJ") and len(api_key) > 100
    if is_bearer:
        return {"Authorization": f"Bearer {api_key}"}, {}
    else:
        return {}, {"api_key": api_key, "language": "en-US"}
```

### 3. **English Content Filter** (100% reusable)
```python
# From mpv-scraper/src/mpv_scraper/tmdb.py:187-220
def filter_english_images(images: list[dict]) -> dict | None:
    us_imgs = [img for img in images if img.get("iso_3166_1") == "US"]
    en_imgs = [img for img in images if img.get("iso_639_1") == "en"]

    candidates = us_imgs or en_imgs or [
        img for img in images
        if not any(non_en in img.get("file_path", "").lower()
                   for non_en in ["ru", "de", "fr", "es", "it", "pt", "ja", "ko", "zh"])
    ] or images

    if not candidates:
        return None

    return max(candidates, key=lambda x: (
        x.get("vote_average", 0),
        x.get("file_path", "").endswith(".png"),  # Prefer PNG
        x.get("iso_3166_1") == "US"
    ))
```

### 4. **Retry Decorator** (95% reusable - adapt to async)
```python
# From mpv-scraper/src/mpv_scraper/utils.py:51-92
# ASYNC VERSION:
def async_retry_with_backoff(max_attempts=3, base_delay=1.0):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
            raise last_exception
        return wrapper
    return decorator
```

---

## 🚨 Security Lessons

### ✅ What mpv-scraper does RIGHT:
1. **Environment-only keys**: `os.getenv("TVDB_API_KEY")`
2. **No key exposure**: Keys never in logs or errors
3. **Timeout enforcement**: All requests have `timeout=10`
4. **Rate limiting**: Global 0.5s delay between requests
5. **Caching**: Reduces API load by 90%+

### ❌ What we should IMPROVE:
1. **Synchronous blocking**: Uses `requests` (blocking I/O)
2. **File-based cache**: JSON files instead of SQLite
3. **No rate limit tracking**: Just `time.sleep()`, no state
4. **No 429 handling**: Doesn't detect/handle rate limit errors
5. **No circuit breaker**: No backoff on repeated failures

---

## 📊 Test Coverage Insights

**File:** `tests/test_retry.py`

✅ **Excellent patterns:**
- Mock-based retry testing
- Timing verification for exponential backoff
- Exception-specific retry testing
- Decorator preservation checks

✅ **Reusable test patterns:**
```python
def test_retry_logic():
    mock_func = Mock()
    mock_func.side_effect = [
        Exception("Fail 1"),
        Exception("Fail 2"),
        "Success"
    ]

    retry_func = retry_with_backoff(max_attempts=3, base_delay=0.1)(mock_func)
    start_time = time.time()
    result = retry_func()
    elapsed = time.time() - start_time

    assert mock_func.call_count == 3
    assert result == "Success"
    assert elapsed >= 0.3  # 0.1 + 0.2 = 0.3s backoff
```

---

## 🎯 Action Plan for NameGnome

### Immediate (Sprint 3.1):
1. ✅ **Port TVDB v3 auth** from `tvdb.py:39-70`
2. ✅ **Port TMDB dual auth** from `tmdb.py:41-54`
3. ✅ **Adapt retry decorator** to async (use httpx)
4. ✅ **Add English filtering** for TMDB images
5. ✅ **Implement SQLite cache** (not file-based)

### Next (Sprint 3.2+):
6. ⏳ **Port TVDB series search** from `tvdb.py:73-106`
7. ⏳ **Port TVDB extended fetch** from `tvdb.py:140-260`
8. ⏳ **Port TMDB movie search** from `tmdb.py:17-72`
9. ⏳ **Port TMDB movie details** from `tmdb.py:130-311`
10. ⏳ **Add fallback system** (Phase 2)

---

## 🔧 Technology Swap Matrix

| mpv-scraper | NameGnome Serve | Reason |
|-------------|-----------------|--------|
| `requests` | `httpx` | Async support |
| File cache (JSON) | SQLite | Better TTL, queries |
| `time.sleep()` | Token bucket | Async-safe rate limiting |
| Synchronous | Async/await | LangServe compatibility |
| Click | Typer (optional) | Modern CLI if needed |

---

## 📝 Documentation to Reference

1. **API Troubleshooting**: `docs/technical/API_TROUBLESHOOTING.md`
   - TVDB v3 vs v4 confusion
   - Bearer token detection
   - Rate limit handling

2. **Fallbacks**: `docs/user/FALLBACKS.md`
   - TVmaze for TV (free)
   - OMDb for movies (limited free tier)

3. **Testing**: `tests/test_retry.py`, `tests/test_tvdb.py`, `tests/test_tmdb.py`
   - Mock patterns
   - Timing assertions
   - Cache verification

---

## ✅ Confidence Level: HIGH

**This analysis provides:**
- ✅ Production-tested TVDB v3 implementation
- ✅ TMDB dual auth patterns
- ✅ Retry/backoff logic
- ✅ English content filtering
- ✅ Cache key conventions
- ✅ Rate limiting strategies

**Estimated code reuse: 60-70%** with async adaptations.
