# Performance Optimization Report: `/api/recommend` Latency & Database Queries

This report details an analysis of the Edu Video Recommender backend, focusing on the `/api/recommend` endpoint and database interactions. The goal is to identify bottlenecks causing latency and provide actionable recommendations for optimization.

---

## 1. Architectural & Routing Bottlenecks

### 1.1 Synchronous Operations in Async Endpoints
**Finding**:
The FastApi application is structured with `async def` endpoints, but heavily utilizes synchronous operations under the hood. Specifically, in `backend/app.py`, the `get_recommendations` endpoint is marked `async def`, yet it calls `log_search` and `recommend` from `scraper/semantic_search.py`, both of which execute blocking network requests (to Cloudflare, YouTube) and blocking database queries (using synchronous SQLAlchemy).
*When a synchronous, blocking operation runs inside an `async def` function in FastAPI, it blocks the entire event loop, severely degrading the application's concurrency and drastically increasing latency under load.*

**Recommendations**:
- **Option A (Quick Fix)**: Change `async def get_recommendations` to `def get_recommendations`. FastAPI will automatically run synchronous `def` endpoints in a separate threadpool, preventing event loop blocking. The same applies to `log_interaction`.
- **Option B (Thorough Fix)**: Refactor the database connections to use `asyncio` and `asyncpg` (e.g., `ext.asyncio` in SQLAlchemy 2.0). Additionally, refactor network requests (Cloudflare AI, YouTube API) to use an asynchronous HTTP client like `httpx` instead of `requests`.

---

## 2. API & Network Latency in `recommend`

### 2.1 Sequential & Blocking External API Calls
**Finding**:
The `recommend` function in `scraper/semantic_search.py` potentially makes two very slow, sequential external calls:
1. `create_query_embedding`: Makes a blocking POST request to Cloudflare Workers AI.
2. `fetch_and_store_videos`: If there aren't enough local results, makes blocking GET requests to the YouTube API (`fetch_videos` and `get_video_details`).
Each network request can add hundreds of milliseconds (or more) to the response time. Running them sequentially while the client waits holds up the HTTP response.

**Recommendations**:
- **Asynchronous requests**: If adopting `httpx`, run independent API calls concurrently where possible.
- **Background tasks**: Fetching new videos from YouTube on a cache miss/empty result should ideally be offloaded to a background task (`fastapi.BackgroundTasks`). The user can be immediately served what is available in the DB (or a fallback text search), while the background task populates the DB for future queries.
- **Caching Embeddings**: Consider caching query embeddings using Redis or an in-memory LRU cache so repeated queries do not incur the Cloudflare API latency.

---

## 3. Database Query Optimizations

### 3.1 Unoptimized Text Search Queries
**Finding**:
In `scraper/semantic_search.py`, `_execute_text_search` runs:
```sql
WHERE (title ILIKE :query ESCAPE '\\' OR description ILIKE :query ESCAPE '\\')
```
`ILIKE` with leading wildcards (`%query%`) forces a full table scan in PostgreSQL, making it extremely slow as the `videos` table grows.

**Recommendations**:
- **Implement Full-Text Search**: Replace `ILIKE` with PostgreSQL's built-in Full-Text Search (FTS). Use `tsvector` on the title and description, and query it using `to_tsquery`. Create a GIN index on the `tsvector` to make text searches instantaneous.

### 3.2 Vector Search Indexing
**Finding**:
The vector search query in `recommend`:
```sql
ORDER BY embedding <=> :query_embedding ASC
```
uses `pgvector`. However, `backend/models.py` does not define a vector index (like HNSW or IVFFlat). Without an index, `pgvector` will perform an exact nearest neighbor search, which is an $O(N)$ full table scan calculating cosine distance for every single vector.

**Recommendations**:
- **Add a Vector Index**: Add an HNSW (Hierarchical Navigable Small World) index to the `embedding` column in the `videos` table to ensure scalable, low-latency nearest neighbor searches.
  ```python
  from sqlalchemy import Index
  Index('ix_video_embedding_hnsw', Video.embedding, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
  ```

### 3.3 Redundant Queries
**Finding**:
In `recommend`, the code checks `has_any_embeddings = session.query(Video).filter(Video.embedding.isnot(None)).limit(1).first() is not None` on *every single request*.
This check forces a database query before even evaluating the user's input.

**Recommendations**:
- **Cache Global States**: This check is static and should be done once at application startup or cached heavily, rather than querying the DB on every single `/api/recommend` request.

### 3.4 Connection Pooling Settings
**Finding**:
In `backend/database.py`, the connection pool size is:
`pool_size=10, max_overflow=20`
If changing endpoints to standard synchronous `def`, FastAPI's threadpool default size is 40. This means 40 concurrent requests could exhaust the connection pool (10 + 20 = 30 max connections), leading to queuing and high latency (or timeouts) under load.

**Recommendations**:
- Ensure `pool_size` + `max_overflow` is greater than or equal to the maximum number of worker threads to avoid connection starvation latency.

---

## 4. Code & Loop Inefficiencies

### 4.1 Redundant Counting logic
**Finding**:
In `recommend`, `semantic_count` is evaluated using `COUNT(*)` which scans rows. Later, `_execute_text_search` or vector search is executed again fetching actual rows.
**Recommendation**:
Avoid running count queries if you're going to fetch the rows anyway. Alternatively, limit the impact of counting by relying strictly on `LIMIT` clauses during the fetch phase and reacting if the returned set is too small.

### 4.2 Local filtering vs DB Filtering
**Finding**:
In `scraper/youtube_scraper.py`, `is_youtube_short` evaluates the video duration and skips shorts. This is mostly fine for API results, but it means the code parses durations in Python loops.
**Recommendation**:
It is currently acceptable, but if bulk inserts become a latency factor, processing these API responses concurrently would reduce blocking time.

## Summary of Priority Actions
1. **Critical**: Change `async def get_recommendations` to `def get_recommendations` in `app.py` to prevent event-loop blocking.
2. **Critical**: Add an HNSW index to the pgvector `embedding` column in `models.py`.
3. **High**: Implement Full-Text Search (tsvector/GIN) instead of `ILIKE`.
4. **Medium**: Move YouTube API fetching to a background task so it doesn't block user requests.
