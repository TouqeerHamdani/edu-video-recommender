from sentence_transformers import SentenceTransformer
import numpy as np
from scraper.db import get_connection
from scraper.youtube_scraper import fetch_videos as yt_fetch_videos, get_video_details, insert_video
from scraper.onnx_model import embed_text_onnx, embed_batch_onnx, get_memory_usage
import isodate
import gc
import time
from functools import lru_cache

# Load model lazily to save memory
_model = None

def get_model():
    global _model
    if _model is None:
        try:
            # Use a much smaller model (61MB vs 100MB+)
            _model = SentenceTransformer('all-MiniLM-L6-v2')
            print("Loaded all-MiniLM-L6-v2 model (smaller, faster)")
        except Exception as e:
            print(f"Failed to load ML model: {e}")
            _model = None
    return _model

def embed_text(text):
    """Embed text using ONNX model with Railway memory optimization"""
    try:
        return embed_text_onnx(text)
    except Exception as e:
        print(f"ONNX embedding failed, falling back to original: {e}")
        model = get_model()
        result = model.encode(text, convert_to_numpy=True)
        # Clean up immediately for Railway
        del model
        gc.collect()
        return result

@lru_cache(maxsize=500)  # Reduced cache size for Railway
def embed_text_cached(text):
    """Cached version of embed_text for repeated queries"""
    return embed_text(text)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

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
    import isodate
    conn = get_connection()
    cursor = conn.cursor()

    print(f"Searching for: '{query}' (duration: {video_duration})")
    start_time = time.time()
    
    # Monitor memory usage
    initial_memory = get_memory_usage()
    print(f"Initial memory usage: {initial_memory:.1f} MB")

    # Fetch embedding from DB as well
    cursor.execute("SELECT video_id, title, description, thumbnail, channel, duration, embedding FROM videos")
    rows = cursor.fetchall()
    
    # Use cached embedding for query
    query_embedding = embed_text_cached(query)
    videos = []
    seen_ids = set()

    def duration_in_range(duration_seconds, filter_type):
        if filter_type == "short":
            return duration_seconds < 4 * 60
        elif filter_type == "medium":
            return 4 * 60 <= duration_seconds < 20 * 60
        elif filter_type == "long":
            return duration_seconds >= 20 * 60
        else:
            return True  # 'any'

    # Process videos in smaller batches for Railway memory constraints
    texts_to_embed = []
    video_data = []
    
    for row in rows:
        video_id, title, desc, thumb, channel, duration_iso, embedding = row
        try:
            duration_seconds = isodate.parse_duration(duration_iso).total_seconds()
        except Exception:
            continue  # skip if can't parse
        if not duration_in_range(duration_seconds, video_duration):
            continue  # skip if not in range
            
        full_text = f"{title} {desc}"
        
        # Use cached embedding if present, else prepare for batch embedding
        if embedding is not None:
            video_embedding = np.array(embedding)
            semantic_score = cosine_similarity(query_embedding, video_embedding)
            
            if semantic_score > 0.3:
                videos.append({
                    "video_id": video_id,
                    "title": title,
                    "description": desc,
                    "thumbnail": thumb,
                    "channel": channel,
                    "link": f"https://www.youtube.com/watch?v={video_id}",
                    "score": float(semantic_score)
                })
                seen_ids.add(video_id)
        else:
            # Prepare for batch embedding
            texts_to_embed.append(full_text)
            video_data.append({
                "video_id": video_id,
                "title": title,
                "description": desc,
                "thumbnail": thumb,
                "channel": channel,
                "duration_seconds": duration_seconds
            })
    
    # Batch embed remaining videos with smaller batch size for Railway
    if texts_to_embed:
        try:
            # Use smaller batch size for Railway memory constraints
            batch_embeddings = embed_batch_onnx(texts_to_embed, batch_size=8)
            
            for i, video_info in enumerate(video_data):
                video_embedding = batch_embeddings[i]
                semantic_score = cosine_similarity(query_embedding, video_embedding)
                
                if semantic_score > 0.3:
                    videos.append({
                        "video_id": video_info["video_id"],
                        "title": video_info["title"],
                        "description": video_info["description"],
                        "thumbnail": video_info["thumbnail"],
                        "channel": video_info["channel"],
                        "link": f"https://www.youtube.com/watch?v={video_info['video_id']}",
                        "score": float(semantic_score)
                    })
                    seen_ids.add(video_info["video_id"])
        except Exception as e:
            print(f"Batch embedding failed: {e}")

    # If we have fewer than top_n, fetch more from YouTube
    if len(videos) < top_n:
        print(f"Only {len(videos)} videos found in DB — fetching more from YouTube...")
        yt_results = yt_fetch_videos(query, max_results=top_n*2, video_duration=video_duration)
        video_ids = [item["id"]["videoId"] for item in yt_results if "videoId" in item["id"]]
        print(f"YouTube API returned {len(video_ids)} video IDs.")

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
                semantic_score = cosine_similarity(query_embedding, embed_text(full_text))

                views = int(video["statistics"].get("viewCount", 0))
                likes = int(video["statistics"].get("likeCount", 0))
                popularity_score = (views + 2 * likes) / 1_000_000

                final_score = 0.7 * semantic_score + 0.3 * popularity_score

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

                insert_video(conn, video, subject="Auto", difficulty="Medium")

                if len(videos) >= top_n:
                    break

    conn.close()
    
    # Force garbage collection to free memory for Railway
    gc.collect()
    
    elapsed_time = time.time() - start_time
    final_memory = get_memory_usage()
    print(f"Search completed in {elapsed_time:.2f} seconds")
    print(f"Final memory usage: {final_memory:.1f} MB")
    print(f"Memory delta: {final_memory - initial_memory:.1f} MB")
    
    return sorted(videos, key=lambda v: v["score"], reverse=True)[:top_n]

def log_search(query, user_id="guest"):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO user_searches (user_id, query) VALUES (%s, %s)",
            (user_id, query)
        )
        conn.commit()
    conn.close()

def get_user_profile(user_id):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT query FROM user_searches WHERE user_id = %s ORDER BY search_time DESC LIMIT 10",
            (user_id,)
        )
        queries = [row[0] for row in cur.fetchall()]
    conn.close()

    if not queries:
        return None

    embeddings = [embed_text(q) for q in queries]
    return np.mean(embeddings, axis=0)

def check_query_in_db(query):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT video_id, title, description, channel, thumbnail
            FROM videos
            WHERE title ILIKE %s OR description ILIKE %s
            LIMIT 20
        """, (f"%{query}%", f"%{query}%"))
        rows = cur.fetchall()
    conn.close()

    return [
        {
            'video_id': row[0],
            'title': row[1],
            'description': row[2],
            'channel': row[3],
            'thumbnail': row[4],
            'link': f"https://www.youtube.com/watch?v={row[0]}"
        }
        for row in rows
    ]

if __name__ == "__main__":
    results = recommend("atom class 11", top_n=10, user_id="test_user")
    for video in results:
        print(f"Title: {video['title']}")
        print(f"Channel: {video['channel']}")
        print(f"Score: {video['score']:.4f}")
        print(f"Link: {video['link']}")
        print()
