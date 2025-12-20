import numpy as np
import time
from functools import lru_cache
# from sentence_transformers import SentenceTransformer  # Disabled for Phase 1
from backend.database import get_session
from backend.models import Video, UserSearch
from scraper.youtube_scraper import fetch_videos as yt_fetch_videos, get_video_details, insert_video
import isodate
from sqlalchemy import text
from sqlalchemy.orm import joinedload

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

def is_probable_short(video):
    """
    Returns True if video is likely a Short: duration < 60s or contains '#shorts' in title/description.
    """
    try:
        iso_duration = video["contentDetails"]["duration"]
        duration_seconds = isodate.parse_duration(iso_duration).total_seconds()
    except Exception as e:
        print(f"⚠️ Failed to parse duration: {e}")
        return True  # Assume short if unsure

    title = video["snippet"]["title"].lower()
    description = video["snippet"]["description"].lower()

    return duration_seconds < 60 or "#shorts" in title or "#shorts" in description

def recommend(query, top_n=5, user_id="guest", video_duration="medium"):
    try:
        session = get_session()

        print(f"Searching for: '{query}' (duration: {video_duration})")
        start_time = time.time()

        # Phase 1: Use text search instead of embeddings
        # query_embedding = embed_text_cached(query)
        # if query_embedding is None:
        #     print("[ERROR] Failed to embed query")
        #     return []

        # Build duration filter
        duration_filter = ""
        if video_duration == "short":
            duration_filter = "AND duration < 240"  # < 4 minutes
        elif video_duration == "medium":
            duration_filter = "AND duration >= 240 AND duration < 1200"  # 4-20 minutes
        elif video_duration == "long":
            duration_filter = "AND duration >= 1200"  # >= 20 minutes

        # Phase 1: Use text search instead of pgvector
        sql = f"""
        SELECT
            youtube_id,
            title,
            description,
            thumbnail,
            duration,
            view_count,
            like_count
        FROM videos
        WHERE (title ILIKE :query OR description ILIKE :query)
        {duration_filter}
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
        video_ids = []

        for row in result:
            youtube_id, title, description, thumbnail, duration, view_count, like_count = row

            if youtube_id in seen_ids:
                continue

            videos.append({
                "video_id": youtube_id,
                "title": title,
                "description": description,
                "thumbnail": thumbnail,
                "channel": "YouTube",  # We don't store channel in new schema
                "link": f"https://www.youtube.com/watch?v={youtube_id}",
                "score": float(view_count + 2 * like_count) / 100000,  # Popularity score for Phase 1
                "views": view_count,
                "likes": like_count
            })
            seen_ids.add(youtube_id)
            video_ids.append(youtube_id)

        session.close()

        if video_ids:
                video_details = get_video_details(video_ids)

                for video in video_details:
                    try:
                        iso_duration = video["contentDetails"]["duration"]
                        duration_seconds = isodate.parse_duration(iso_duration).total_seconds()
                    except Exception as e:
                        print(f"Failed to parse duration: {e}")
                        continue

                    # Strict duration filtering
                    if not duration_in_range(duration_seconds, video_duration):
                        print(f"Skipped: {video['snippet']['title']} — duration {duration_seconds/60:.1f} min not in range for {video_duration}.")
                        continue

                    vid_id = video["id"]
                    if vid_id in seen_ids:
                        print(f"Skipped: {video['snippet']['title']} — duplicate video ID.")
                        continue  # skip duplicates

                    if is_probable_short(video):
                        print(f"Skipped: {video['snippet']['title']} — likely a Short.")
                        continue

                    if video["snippet"].get("categoryId") != "27":
                        print(f"Skipped: {video['snippet']['title']} — not educational.")
                        continue

                    title = video["snippet"]["title"]
                    desc = video["snippet"]["description"]
                    full_text = f"{title} {desc}"
                    # Phase 1: No embeddings
                    # semantic_score = cosine_similarity(query_embedding, embed_text(full_text))
                    semantic_score = 0.5  # Placeholder

                    views = int(video["statistics"].get("viewCount", 0))
                    likes = int(video["statistics"].get("likeCount", 0))
                    popularity_score = (views + 2 * likes) / 1_000_000

                    final_score = popularity_score  # Phase 1: Only popularity

                    videos.append({
                        "video_id": vid_id,
                        "title": title,
                        "description": desc,
                        "thumbnail": video["snippet"]["thumbnails"]["high"]["url"],
                        "channel": video["snippet"]["channelTitle"],
                        "link": f"https://www.youtube.com/watch?v={vid_id}",
                        "score": float(final_score)
                    })
                    seen_ids.add(vid_id)

                    # insert_video(video, subject="Auto", difficulty="Medium")  # Removed as videos are already in DB

                    if len(videos) >= top_n:
                        break

        elapsed_time = time.time() - start_time
        print(f"Search completed in {elapsed_time:.2f} seconds")
        
        return sorted(videos, key=lambda v: v["score"], reverse=True)[:top_n]
        
    except Exception as e:
        print(f"[ERROR] Recommend failed: {e}")
        return []

def log_search(query, user_id="guest"):
    """Log user search query using SQLAlchemy ORM."""
    session = get_session()
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
        session.close()

def get_user_profile(user_id):
    """Get user's search history and compute average embedding for personalization."""
    session = get_session()
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
        searches = session.query(UserSearch).filter(
            UserSearch.user_id == user_uuid
        ).order_by(UserSearch.search_time.desc()).limit(10).all()

        queries = [search.query for search in searches]
        session.close()

        if not queries:
            return None

        embeddings = [embed_text(q) for q in queries if embed_text(q) is not None]
        if not embeddings:
            return None

        return np.mean(embeddings, axis=0)
    except Exception as e:
        print(f"Failed to get user profile: {e}")
        session.close()
        return None

def check_query_in_db(query):
    session = get_session()
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
        session.close()

if __name__ == "__main__":
    results = recommend("atom class 11", top_n=10, user_id="test_user")
    for video in results:
        print(f"Title: {video['title']}")
        print(f"Channel: {video['channel']}")
        print(f"Score: {video['score']:.4f}")
        print(f"Link: {video['link']}")
        print()
