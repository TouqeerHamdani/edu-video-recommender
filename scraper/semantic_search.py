import time
import os
import logging

import requests
import numpy as np
from sqlalchemy import text

from backend.database import get_session
from backend.models import UserSearch, Video

# Cloudflare Workers AI configuration
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_BGE_URL = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/baai/bge-small-en-v1.5"


def create_query_embedding(query):
    """
    Create query embedding using Cloudflare Workers AI bge-small-en-v1.5.
    Returns 384-dimensional embedding for vector search.
    """
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        logging.warning("Cloudflare credentials not set. Vector search disabled.")
        return None
    
    try:
        response = requests.post(
            CLOUDFLARE_BGE_URL,
            headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"},
            json={"text": query},
            timeout=10
        )
        
        if response.status_code != 200:
            logging.error(f"Cloudflare API error: {response.status_code} - {response.text}")
            return None
        
        result = response.json()
        
        # Extract embedding from response
        if result.get("success") and result.get("result", {}).get("data"):
            embedding = result["result"]["data"][0]
            return np.array(embedding, dtype=np.float32)
        else:
            logging.error(f"Unexpected Cloudflare response: {result}")
            return None
        
    except Exception as e:
        logging.error(f"Failed to create query embedding: {e}")
        return None


def create_query_embeddings(queries):
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
        response = requests.post(
            CLOUDFLARE_BGE_URL,
            headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"},
            json={"text": queries},
            timeout=30
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
        emb = create_query_embedding(q)
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


def _get_local_session():
    """Helper to get a session from the generator manually."""
    gen = get_session()
    session = next(gen)
    return session, gen


def _escape_like(query):
    """Escape SQL LIKE/ILIKE wildcard characters in user input."""
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _execute_text_search(session, query, duration_filter_sql, limit):
    """Run a text-based ILIKE search and return the raw result rows."""
    sql = f"""
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
    WHERE (title ILIKE :query ESCAPE '\\' OR description ILIKE :query ESCAPE '\\')
    {duration_filter_sql}
    ORDER BY view_count DESC NULLS LAST, like_count DESC NULLS LAST
    LIMIT :limit
    """
    return session.execute(
        text(sql),
        {"query": f"%{_escape_like(query)}%", "limit": limit}
    )


def _process_text_rows(rows, seen_ids, videos):
    """Map raw text-search result rows to video dicts. Mutates seen_ids and videos in-place."""
    for row in rows:
        youtube_id, title, description, thumbnail, duration, view_count, like_count, _similarity = row
        if youtube_id in seen_ids:
            continue
        view_count = view_count or 0
        like_count = like_count or 0
        videos.append({
            "video_id": youtube_id,
            "title": title,
            "description": description,
            "thumbnail": thumbnail,
            "channel": "YouTube",
            "link": f"https://www.youtube.com/watch?v={youtube_id}",
            "score": float(view_count + 2 * like_count) / 100000,
            "views": view_count,
            "likes": like_count
        })
        seen_ids.add(youtube_id)

def recommend(query, top_n=5, user_id="guest", video_duration="any", db_session=None):
    session = None
    session_gen = None
    
    # Use provided session or create a new one
    if db_session:
        session = db_session
    else:
        session, session_gen = _get_local_session()

    try:
        print(f"Searching for: '{query}' (duration: {video_duration})")
        start_time = time.time()
        
        # === STEP 1: Build duration filter + generate query embedding ===
        from scraper.youtube_scraper import fetch_and_store_videos

        # Build duration filter
        duration_filter_sql = ""
        if video_duration == "short":
            duration_filter_sql = "AND duration < 240"  # < 4 minutes
        elif video_duration == "medium":
            duration_filter_sql = "AND duration >= 240 AND duration < 1200"  # 4-20 minutes
        elif video_duration == "long":
            duration_filter_sql = "AND duration >= 1200"  # >= 20 minutes

        # Check globally if ANY video in the DB has an embedding
        has_any_embeddings = session.query(Video).filter(
            Video.embedding.isnot(None)
        ).limit(1).first() is not None

        query_vector = None
        embedding_list = None
        if has_any_embeddings:
            query_vector = create_query_embedding(query)
            if query_vector is not None:
                embedding_list = query_vector.tolist() if hasattr(query_vector, 'tolist') else query_vector
        else:
            print("⏭️ Skipping embedding — no embedded videos exist in DB")

        # === STEP 2: Smart supply check — decide if YouTube fetch is needed ===
        if query_vector is not None:
            # Use vector similarity count: how many DB videos are semantically close?
            count_sql = f"""
                SELECT COUNT(*) FROM videos
                WHERE embedding IS NOT NULL
                AND 1 - (embedding <=> :qe) > 0.6
                {duration_filter_sql}
            """
            semantic_count = session.execute(
                text(count_sql), {"qe": str(embedding_list)}
            ).scalar() or 0
            print(f"📊 Found {semantic_count} semantically relevant videos in DB (similarity > 0.6)")
            needs_youtube = semantic_count < top_n
        else:
            # Fallback: ILIKE text match count
            db_videos, _ = check_query_in_db(query, video_duration=video_duration, db_session=session)
            db_count = len(db_videos) if db_videos else 0
            print(f"📊 Found {db_count} keyword-matching videos in DB (duration: {video_duration})")
            needs_youtube = db_count < top_n

        # === STEP 3: Fetch from YouTube if not enough ===
        if needs_youtube:
            print(f"⚠️ Not enough relevant videos in DB, fetching from YouTube...")
            try:
                inserted = fetch_and_store_videos(
                    query,
                    max_results=20,
                    video_duration=video_duration,
                    db_session=session
                )
                if inserted > 0:
                    session.commit()
                    print(f"✅ Added {inserted} new videos from YouTube")
            except Exception as yt_error:
                print(f"⚠️ YouTube fetch failed: {yt_error}")

        # === STEP 4: Search and recommend from database ===
        
        if query_vector is not None:
            print("Using Vector Search (pgvector)")
            # Use pgvector cosine distance operator <=>
            # Order by distance (ASC) because lower distance = higher similarity
            sql = f"""
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
            {duration_filter_sql}
            ORDER BY embedding <=> :query_embedding ASC
            LIMIT :limit
            """
            
            
            result = session.execute(
                text(sql),
                {
                    "query_embedding": str(embedding_list), # pgvector expects string representation or array
                    "limit": top_n
                }
            )
        else:
            print("Using Text Search (Fallback - ILIKE)")
            result = _execute_text_search(session, query, duration_filter_sql, top_n)

        videos = []
        seen_ids = set()

        if query_vector is not None:
            # Vector search: use similarity score
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
        else:
            # Text search: use popularity score
            _process_text_rows(result, seen_ids, videos)

        # Fallback: if vector search returned 0 results (e.g. new videos without embeddings),
        # retry with text search so freshly fetched YouTube videos still appear
        if not videos and query_vector is not None:
            print("⚠️ Vector search returned 0 results, falling back to text search...")
            fallback_result = _execute_text_search(session, query, duration_filter_sql, top_n)
            _process_text_rows(fallback_result, seen_ids, videos)

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

        # Only close if we created it
        if session_gen:
            session_gen.close()

        elapsed_time = time.time() - start_time
        print(f"Search completed in {elapsed_time:.2f} seconds")
        
        return sorted(videos, key=lambda v: v["score"], reverse=True)[:top_n]
        
    except Exception as e:
        print(f"[ERROR] Recommend failed: {e}")
        # Ensure cleanup on error
        if session_gen:
            session_gen.close()
        return []

def log_search(query, user_id="guest", db_session=None):
    """Log user search query using SQLAlchemy ORM."""
    session = None
    session_gen = None
    
    if db_session:
        session = db_session
    else:
        session, session_gen = _get_local_session()

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
            if not db_session:
                session.commit()  # Only commit if we own the session
    except Exception as e:
        print(f"Failed to log search: {e}")
        if not db_session:
            session.rollback()  # Only rollback if we own the session
    finally:
        if session_gen:
            session_gen.close()

def get_user_profile(user_id, db_session=None):
    """Get user's search history and compute average embedding for personalization."""
    session = None
    session_gen = None
    
    if db_session:
        session = db_session
    else:
        session, session_gen = _get_local_session()

    try:
        # Convert string user_id to UUID if needed
        from uuid import UUID
        if isinstance(user_id, str):
            try:
                user_uuid = UUID(user_id)
            except ValueError:
                if session_gen: session_gen.close()
                return None  # Invalid UUID
        else:
            user_uuid = user_id

        # Get recent search queries for this user
        searches = session.query(UserSearch).filter(
            UserSearch.user_id == user_uuid
        ).order_by(UserSearch.search_time.desc()).limit(10).all()

        queries = [search.query for search in searches]
        # cleanup
        if session_gen: session_gen.close()

        if not queries:
            return None

        embeddings = create_query_embeddings(queries)
        if not embeddings:
            return None

        return np.mean(embeddings, axis=0)
    except Exception as e:
        print(f"Failed to get user profile: {e}")
        if session_gen:
            session_gen.close()
        return None

def check_query_in_db(query, video_duration="any", db_session=None):
    session = None
    session_gen = None
    
    if db_session:
        session = db_session
    else:
        session, session_gen = _get_local_session()

    try:
        # Base text filter (escape SQL wildcards in user input)
        escaped = _escape_like(query)
        pattern = f"%{escaped}%"
        text_filter = Video.title.ilike(pattern, escape='\\') | Video.description.ilike(pattern, escape='\\')
        q = session.query(Video).filter(text_filter)

        # Apply duration filter if specified
        duration_filter = _build_duration_orm_filter(video_duration)
        if duration_filter is not None:
            q = q.filter(duration_filter)

        videos = q.limit(20).all()

        # Check if any of the matched videos have embeddings
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
        if session_gen:
            session_gen.close()

if __name__ == "__main__":
    results = recommend("atom class 11", top_n=10, user_id="test_user")
    for video in results:
        print(f"Title: {video['title']}")
        print(f"Channel: {video['channel']}")
        print(f"Score: {video['score']:.4f}")
        print(f"Link: {video['link']}")
        print()
