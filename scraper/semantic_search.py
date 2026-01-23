import time

import isodate
import numpy as np
from sqlalchemy import text

# from sentence_transformers import SentenceTransformer  # Disabled for Phase 1
from backend.database import get_session
from backend.models import UserSearch, Video

# Global model instance for memory efficiency
_model = None

# def get_model():  # Disabled for Phase 1
#     global _model
#     if _model is None:
#         try:
#             # Use a verified tiny SBERT model that actually exists
#             _model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')  # 384 dimensions, 90MB
#             print("Loaded sentence-transformers/all-MiniLM-L6-v2 model (verified)")
#         except Exception as e:
#             print(f"Failed to load ML model: {e}")
#             _model = None
#     return _model

# def embed_text(text):  # Disabled for Phase 1
#     """Embed text using SentenceTransformer with Railway memory optimization"""
#     try:
#         model = get_model()
#         if model is None:
#             raise Exception("Model not loaded")
#         result = model.encode(text, convert_to_numpy=True)
#         # Don't delete model - keep it in memory for next request
#         return result
#     except Exception as e:
#         print(f"Embedding failed: {e}")
#         return None

# def embed_batch(texts, batch_size=8):  # Disabled for Phase 1
#     """Embed batch of texts using SentenceTransformer"""
#     try:
#         model = get_model()
#         if model is None:
#             raise Exception("Model not loaded")
#         # Use smaller batch size for Railway memory constraints
#         results = model.encode(texts, batch_size=batch_size, convert_to_numpy=True)
#         return results
#     except Exception as e:
#         print(f"Batch embedding failed: {e}")
#         return None

# @lru_cache(maxsize=500)  # Reduced cache size for Railway
# def embed_text_cached(text):  # Disabled for Phase 1
#     """Cached version of embed_text for repeated queries"""
#     return embed_text(text)

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




def create_query_embedding(query):
    """
    Attempt to create a query embedding. 
    Use the local model if loaded/enabled.
    """
    try:
        # Check if local model can be loaded (Phase 2 or testing)
        if _model:
             return _model.encode(query, convert_to_numpy=True)
        
        # If no model, we cannot do vector search unless we use an external API.
        # For now, return None to trigger fallback.
        # To enable local model for testing, uncomment get_model() at top.
        return None
    except Exception as e:
        print(f"Failed to create query embedding: {e}")
        return None

def _get_local_session():
    """Helper to get a session from the generator manually."""
    gen = get_session()
    session = next(gen)
    return session, gen

def recommend(query, top_n=5, user_id="guest", video_duration="medium", db_session=None):
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
        
        # === STEP 1: Check if we have enough videos in DB ===
        from scraper.youtube_scraper import fetch_and_store_videos
        
        # Count matching videos in database
        db_videos = check_query_in_db(query, db_session=session)
        db_count = len(db_videos) if db_videos else 0
        print(f"📊 Found {db_count} matching videos in database")
        
        # === STEP 2: If not enough, fetch from YouTube API ===
        if db_count < top_n:
            print(f"⚠️ Not enough videos in DB ({db_count} < {top_n}), fetching from YouTube...")
            try:
                inserted = fetch_and_store_videos(
                    query, 
                    max_results=20, 
                    video_duration=video_duration,
                    db_session=session
                )
                if inserted > 0:
                    session.commit()  # Commit newly inserted videos
                    print(f"✅ Added {inserted} new videos from YouTube")
            except Exception as yt_error:
                print(f"⚠️ YouTube fetch failed: {yt_error}")
                # Continue with whatever we have in DB
        
        # === STEP 3: Search and recommend from database ===

        # Build duration filter
        duration_filter_sql = ""
        if video_duration == "short":
            duration_filter_sql = "AND duration < 240"  # < 4 minutes
        elif video_duration == "medium":
            duration_filter_sql = "AND duration >= 240 AND duration < 1200"  # 4-20 minutes
        elif video_duration == "long":
            duration_filter_sql = "AND duration >= 1200"  # >= 20 minutes

        # Attempt to get query embedding
        query_vector = create_query_embedding(query)
        
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
            WHERE 1=1
            {duration_filter_sql}
            ORDER BY embedding <=> :query_embedding ASC
            LIMIT :limit
            """
            
            # Convert numpy array to list for SQLAlchemy
            embedding_list = query_vector.tolist() if hasattr(query_vector, 'tolist') else query_vector
            
            result = session.execute(
                text(sql),
                {
                    "query_embedding": str(embedding_list), # pgvector expects string representation or array
                    "limit": top_n
                }
            )
        else:
            print("Using Text Search (Fallback - ILIKE)")
            # Phase 1 Fallback: Use text search
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
            WHERE (title ILIKE :query OR description ILIKE :query)
            {duration_filter_sql}
            ORDER BY view_count DESC, like_count DESC
            LIMIT :limit
            """

            result = session.execute(
                text(sql),
                {
                    "query": f"%{query}%",
                    "limit": top_n
                }
            )

        videos = []
        seen_ids = set()

        for row in result:
            # Unpack 8 columns
            youtube_id, title, description, thumbnail, duration, view_count, like_count, similarity = row

            if youtube_id in seen_ids:
                continue

            # Calculate final score
            # If vector search, use similarity. If text search, use popularity.
            if query_vector is not None:
                final_score = float(similarity)
            else:
                 # Popularity score
                 final_score = float(view_count + 2 * like_count) / 100000

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
            session.commit()
    except Exception as e:
        print(f"Failed to log search: {e}")
        session.rollback()
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

        embeddings = [embed_text(q) for q in queries if embed_text(q) is not None]
        if not embeddings:
            return None

        return np.mean(embeddings, axis=0)
    except Exception as e:
        print(f"Failed to get user profile: {e}")
        if session_gen:
            session_gen.close()
        return None

def check_query_in_db(query, db_session=None):
    session = None
    session_gen = None
    
    if db_session:
        session = db_session
    else:
        session, session_gen = _get_local_session()

    try:
        videos = session.query(Video).filter(
            Video.title.ilike(f"%{query}%") | Video.description.ilike(f"%{query}%")
        ).limit(20).all()

        return [
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
