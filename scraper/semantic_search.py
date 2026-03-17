import logging
import os
import time

import httpx
import numpy as np
from sqlalchemy import text

from backend.models import UserSearch, Video

# Cached after the first request — avoids a per-request DB round-trip (report §3.3).
# Stores {"value": bool, "ts": float} so the result refreshes after _HAS_EMBEDDINGS_TTL
# seconds. This prevents a permanent False when the embedder runs after server startup.
_has_embeddings_cache: dict = {}
_HAS_EMBEDDINGS_TTL = 1800  # seconds (30 min) — embeddings don't disappear; force_refresh=True handles post-embed invalidation


async def _check_has_embeddings(session, force_refresh: bool = False) -> bool:
    """Return True if any video with an embedding exists.

    Result is cached for _HAS_EMBEDDINGS_TTL seconds. Pass force_refresh=True to
    bypass the cache immediately (e.g., after an embedding write batch).
    """
    global _has_embeddings_cache
    now = time.monotonic()
    cached = _has_embeddings_cache
    if (
        not force_refresh
        and cached
        and (now - cached["ts"]) < _HAS_EMBEDDINGS_TTL
    ):
        return cached["value"]

    from sqlalchemy import select
    result = await session.execute(
        select(Video).filter(Video.embedding.isnot(None)).limit(1)
    )
    value = result.scalars().first() is not None
    _has_embeddings_cache = {"value": value, "ts": now}
    return value

# Cloudflare Workers AI configuration
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_BGE_URL = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/baai/bge-small-en-v1.5"

# Server-side embedding cache — keyed by query string, value is the raw float list.
# Embeddings are deterministic so no expiry is needed. Each 384-dim vector ≈ 1.5 KB,
# so 1,000 entries ≈ 1.5 MB. Shared across all requests in this process (report §2.1).
_embedding_cache: dict[str, list] = {}


async def create_query_embedding(query):
    """
    Create query embedding using Cloudflare Workers AI bge-small-en-v1.5.
    Returns 384-dimensional embedding for vector search.
    Result is cached in-process to avoid repeated Cloudflare API calls (report §2.1).
    """
    if query in _embedding_cache:
        return np.array(_embedding_cache[query], dtype=np.float32)

    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        logging.warning("Cloudflare credentials not set. Vector search disabled.")
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                CLOUDFLARE_BGE_URL,
                headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"},
                json={"text": query},
            )

        if response.status_code != 200:
            logging.error(f"Cloudflare API error: {response.status_code} - {response.text}")
            return None

        result = response.json()

        # Extract embedding from response
        if result.get("success") and result.get("result", {}).get("data"):
            embedding = result["result"]["data"][0]
            vector = np.array(embedding, dtype=np.float32)
            _embedding_cache[query] = embedding  # store raw list, not numpy array
            return vector
        else:
            logging.error(f"Unexpected Cloudflare response: {result}")
            return None

    except Exception as e:
        logging.error(f"Failed to create query embedding: {e}")
        return None


async def create_query_embeddings(queries):
    """
    Batch-embed multiple queries in a single Cloudflare API call.
    Falls back to per-query calls on batch failure.
    Returns a list of numpy arrays (None entries filtered out).
    """
    if not queries:
        return []
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        logging.warning("Cloudflare credentials not set. Vector search disabled.")
        return []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                CLOUDFLARE_BGE_URL,
                headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"},
                json={"text": queries},
            )
        if response.status_code == 200:
            result = response.json()
            if result.get("success") and result.get("result", {}).get("data"):
                data = result["result"]["data"]
                return [np.array(emb, dtype=np.float32) for emb in data if emb]
    except Exception as e:
        logging.warning(f"Batch embedding failed, falling back to per-query: {e}")

    # Fallback: per-query calls
    embeddings = []
    for q in queries:
        emb = await create_query_embedding(q)
        if emb is not None:
            embeddings.append(emb)
    return embeddings


def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def duration_in_range(duration_seconds, video_duration):
    """
    Check if duration falls within the specified range.
    """
    if video_duration == "short":
        return duration_seconds < 240  # < 4 minutes
    elif video_duration == "medium":
        return 240 <= duration_seconds < 1200  # 4-20 minutes
    elif video_duration == "long":
        return duration_seconds >= 1200  # >= 20 minutes
    return True  # Default to True if no filter specified


def _build_duration_orm_filter(video_duration):
    """Build SQLAlchemy ORM filter conditions for duration."""
    from sqlalchemy import and_
    if video_duration == "short":
        return Video.duration < 240
    elif video_duration == "medium":
        return and_(Video.duration >= 240, Video.duration < 1200)
    elif video_duration == "long":
        return Video.duration >= 1200
    return None  # "any" or unrecognized — no filter


def _get_local_async_session():
    """Return a new AsyncSession for non-web contexts (eval scripts, standalone use)."""
    from backend.database import AsyncSessionLocal
    return AsyncSessionLocal()


def _escape_like(query):
    """Escape SQL LIKE/ILIKE wildcard characters in user input."""
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def _execute_text_search(session, query, min_duration, max_duration, limit):
    """Run a full-text search using the GIN tsvector index (report §3.1).

    Uses websearch_to_tsquery which handles multi-word phrases and quoted
    strings without needing manual query escaping.
    """
    sql = """
    SELECT
        youtube_id,
        title,
        description,
        thumbnail,
        duration,
        view_count,
        like_count,
        0.0 as similarity_score
    FROM videos
    WHERE to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))
          @@ websearch_to_tsquery('english', :query)
          AND (:min_duration::int IS NULL OR duration >= :min_duration)
          AND (:max_duration::int IS NULL OR duration < :max_duration)
    ORDER BY view_count DESC NULLS LAST, like_count DESC NULLS LAST
    LIMIT :limit
    """
    return await session.execute(
        text(sql),
        {
            "query": query,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "limit": limit
        }
    )


def _process_text_rows(rows, seen_ids, videos, base_score=None):
    """Map raw text-search result rows to video dicts. Mutates seen_ids and videos in-place."""
    for row in rows:
        youtube_id, title, description, thumbnail, duration, view_count, like_count, _similarity = row
        if youtube_id in seen_ids:
            continue
        view_count = view_count or 0
        like_count = like_count or 0

        # If no base_score provided, use the old popularity-only logic
        if base_score is not None:
            score = base_score
        else:
            score = float(view_count + 2 * like_count) / 100000

        videos.append({
            "video_id": youtube_id,
            "title": title,
            "description": description,
            "thumbnail": thumbnail,
            "channel": "YouTube",
            "link": f"https://www.youtube.com/watch?v={youtube_id}",
            "score": score,
            "views": view_count,
            "likes": like_count
        })
        seen_ids.add(youtube_id)

async def recommend(query, top_n=5, user_id="guest", video_duration="any", db_session=None):
    own_session = False
    if db_session:
        session = db_session
    else:
        session = _get_local_async_session()
        own_session = True

    try:
        print(f"Searching for: '{query}' (duration: {video_duration})")
        start_time = time.time()

        # === STEP 1: Build duration filter + generate query embedding ===
        from scraper.youtube_scraper import fetch_and_store_videos

        # Build duration filter
        min_duration = None
        max_duration = None
        if video_duration == "short":
            max_duration = 240
        elif video_duration == "medium":
            min_duration = 240
            max_duration = 1200
        elif video_duration == "long":
            min_duration = 1200

        # Cached after first request — no DB round-trip on subsequent calls (report §3.3)
        has_any_embeddings = await _check_has_embeddings(session)

        query_vector = None
        embedding_list = None
        if has_any_embeddings:
            query_vector = await create_query_embedding(query)
            if query_vector is not None:
                embedding_list = query_vector.tolist() if hasattr(query_vector, 'tolist') else query_vector
        else:
            print("⏭️ Skipping embedding — no embedded videos exist in DB")

        # === STEP 2: Supply check — LIMIT probe instead of COUNT (report §4.1) ===
        _initial_text_rows = None  # cached FTS rows for reuse in Step 4 (no-embedding path only)
        if query_vector is not None:
            # SELECT 1 ... LIMIT top_n stops at top_n rows — far cheaper than COUNT(*)
            supply_sql = """
                SELECT 1 FROM videos
                WHERE embedding IS NOT NULL
                AND 1 - (embedding <=> :qe) > 0.6
                AND (:min_duration::int IS NULL OR duration >= :min_duration)
                AND (:max_duration::int IS NULL OR duration < :max_duration)
                LIMIT :limit
            """
            supply_rows = (await session.execute(
                text(supply_sql),
                {
                    "qe": str(embedding_list),
                    "min_duration": min_duration,
                    "max_duration": max_duration,
                    "limit": top_n
                }
            )).fetchall()
            print(f"📊 Found {len(supply_rows)} semantically relevant videos in DB (similarity > 0.6)")
            needs_youtube = len(supply_rows) < top_n
        else:
            # Run FTS once and cache rows — reused in Step 4 fallback if no YouTube fetch needed
            _initial_text_rows = (await _execute_text_search(
                session, query, min_duration, max_duration, top_n
            )).fetchall()
            print(f"📊 Found {len(_initial_text_rows)} keyword-matching videos in DB (duration: {video_duration})")
            needs_youtube = len(_initial_text_rows) < top_n

        # === STEP 3: Fetch from YouTube if not enough ===
        if needs_youtube:
            print("⚠️ Not enough relevant videos in DB, fetching from YouTube...")
            try:
                inserted = await fetch_and_store_videos(
                    query,
                    max_results=20,
                    video_duration=video_duration,
                    db_session=session
                )
                if inserted > 0:
                    if own_session:
                        await session.commit()
                    print(f"✅ Added {inserted} new videos from YouTube")
            except Exception as yt_error:
                print(f"⚠️ YouTube fetch failed: {yt_error}")

        # === STEP 4: Search and recommend from database ===

        videos = []
        seen_ids = set()

        # If a fresh fetch was triggered, we PRIORITIZE text results (ILIKE)
        # because the newly inserted videos don't have embeddings yet.
        if needs_youtube:
            print("🚀 Fresh Fetch Priority: Retrieving keyword-matched videos first...")
            text_result = await _execute_text_search(session, query, min_duration, max_duration, top_n)
            _process_text_rows(text_result, seen_ids, videos, base_score=0.7)

        # Then, if we still need more videos, perform Vector Search (pgvector)
        if query_vector is not None and len(videos) < top_n:
            print(f"Using Vector Search (pgvector) for remaining {top_n - len(videos)} slots")
            sql = """
            SELECT
                youtube_id,
                title,
                description,
                thumbnail,
                duration,
                view_count,
                like_count,
                1 - (embedding <=> :query_embedding) as similarity_score
            FROM videos
            WHERE embedding IS NOT NULL
            AND 1 - (embedding <=> :query_embedding) > 0.5
            AND (:min_duration::int IS NULL OR duration >= :min_duration)
            AND (:max_duration::int IS NULL OR duration < :max_duration)
            ORDER BY embedding <=> :query_embedding ASC
            LIMIT :limit
            """

            result = await session.execute(
                text(sql),
                {
                    "query_embedding": str(embedding_list),
                    "min_duration": min_duration,
                    "max_duration": max_duration,
                    "limit": top_n - len(videos)
                }
            )

            for row in result:
                youtube_id, title, description, thumbnail, duration, view_count, like_count, similarity = row
                if youtube_id in seen_ids:
                    continue
                final_score = float(similarity) if similarity is not None else 0.0
                videos.append({
                    "video_id": youtube_id,
                    "title": title,
                    "description": description,
                    "thumbnail": thumbnail,
                    "channel": "YouTube",
                    "link": f"https://www.youtube.com/watch?v={youtube_id}",
                    "score": final_score,
                    "views": view_count,
                    "likes": like_count
                })
                seen_ids.add(youtube_id)

        # Fallback: if we still don't have enough, or if query_vector was skipped
        if len(videos) < top_n:
            text_base = 0.7 if query_vector is not None else None
            # Reuse cached FTS rows when no YouTube fetch occurred — avoids a duplicate query (report §4.1)
            if _initial_text_rows is not None and not needs_youtube:
                print("Using Text Search (Initial Fallback - no embeddings DB-wide)")
                _process_text_rows(_initial_text_rows, seen_ids, videos, base_score=text_base)
            else:
                if query_vector is None:
                    print("Using Text Search (Initial Fallback - no embeddings DB-wide)")
                else:
                    print(f"⚠️ Search still under-quota ({len(videos)}/{top_n}). Filling with text hunt...")
                fallback_result = await _execute_text_search(session, query, min_duration, max_duration, top_n)
                _process_text_rows(fallback_result, seen_ids, videos, base_score=text_base)

        # Blend quality signals into vector search scores:
        # 70% semantic relevance + 30% normalized popularity (views + likes)
        if videos and query_vector is not None:
            max_views = max((v["views"] or 1) for v in videos)
            max_likes = max((v["likes"] or 1) for v in videos)
            for v in videos:
                views_norm = (v["views"] or 0) / max_views
                likes_norm = (v["likes"] or 0) / max_likes
                popularity = 0.5 * views_norm + 0.5 * likes_norm
                v["score"] = 0.7 * v["score"] + 0.3 * popularity

        if own_session:
            await session.close()

        elapsed_time = time.time() - start_time
        print(f"Search completed in {elapsed_time:.2f} seconds")

        return sorted(videos, key=lambda v: v["score"], reverse=True)[:top_n]

    except Exception as e:
        print(f"[ERROR] Recommend failed: {e}")
        if own_session:
            await session.close()
        return []

async def log_search(query, user_id="guest", db_session=None):
    """Log user search query using SQLAlchemy ORM."""
    own_session = False

    if db_session:
        session = db_session
    else:
        session = _get_local_async_session()
        own_session = True

    try:
        # Convert string user_id to UUID if it's not already
        from uuid import UUID
        if isinstance(user_id, str) and user_id != "guest":
            try:
                user_uuid = UUID(user_id)
            except ValueError:
                user_uuid = None  # Invalid UUID, skip logging
        else:
            user_uuid = None  # Guest user or invalid

        if user_uuid:
            search_entry = UserSearch(user_id=user_uuid, query=query)
            session.add(search_entry)
            if own_session:
                await session.commit()
    except Exception as e:
        print(f"Failed to log search: {e}")
        if own_session:
            await session.rollback()
    finally:
        if own_session:
            await session.close()

async def get_user_profile(user_id, db_session=None):
    """Get user's search history and compute average embedding for personalization."""
    own_session = False

    if db_session:
        session = db_session
    else:
        session = _get_local_async_session()
        own_session = True

    try:
        # Convert string user_id to UUID if needed
        from uuid import UUID
        if isinstance(user_id, str):
            try:
                user_uuid = UUID(user_id)
            except ValueError:
                return None  # Invalid UUID
        else:
            user_uuid = user_id

        # Get recent search queries for this user
        from sqlalchemy import select as sa_select
        result = await session.execute(
            sa_select(UserSearch)
            .filter(UserSearch.user_id == user_uuid)
            .order_by(UserSearch.search_time.desc())
            .limit(10)
        )
        searches = result.scalars().all()

        queries = [search.query for search in searches]
        if own_session:
            await session.close()

        if not queries:
            return None

        embeddings = await create_query_embeddings(queries)
        if not embeddings:
            return None

        return np.mean(embeddings, axis=0)
    except Exception as e:
        print(f"Failed to get user profile: {e}")
        if own_session:
            await session.close()
        return None

async def check_query_in_db(query, video_duration="any", db_session=None):
    own_session = False

    if db_session:
        session = db_session
    else:
        session = _get_local_async_session()
        own_session = True

    try:
        from sqlalchemy import or_, select
        escaped = _escape_like(query)
        pattern = f"%{escaped}%"
        stmt = select(Video).where(
            or_(
                Video.title.ilike(pattern, escape='\\'),
                Video.description.ilike(pattern, escape='\\')
            )
        )
        duration_filter = _build_duration_orm_filter(video_duration)
        if duration_filter is not None:
            stmt = stmt.where(duration_filter)
        result = await session.execute(stmt.limit(20))
        videos = result.scalars().all()

        has_embeddings = any(v.embedding is not None for v in videos)

        video_list = [
            {
                'video_id': v.youtube_id,
                'title': v.title,
                'description': v.description,
                'channel': 'YouTube',
                'thumbnail': v.thumbnail,
                'link': f"https://www.youtube.com/watch?v={v.youtube_id}"
            }
            for v in videos
        ]
        return video_list, has_embeddings
    finally:
        if own_session:
            await session.close()

if __name__ == "__main__":
    import asyncio
    results = asyncio.run(recommend("atom class 11", top_n=10, user_id="test_user"))
    for video in results:
        print(f"Title: {video['title']}")
        print(f"Channel: {video['channel']}")
        print(f"Score: {video['score']:.4f}")
        print(f"Link: {video['link']}")
        print()
