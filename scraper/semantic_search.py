import numpy as np
from sentence_transformers import SentenceTransformer
from scraper.db import get_connection
from scraper.youtube_scraper import fetch_videos as yt_fetch_videos, get_video_details, insert_video

# Load model once
model = SentenceTransformer('all-MiniLM-L6-v2')

def embed_text(text):
    return model.encode(text, convert_to_numpy=True)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def recommend(query, top_n=10, user_id="guest"):
    conn = get_connection()
    cursor = conn.cursor()

    print(f"🔍 Searching for: '{query}'")

    cursor.execute("SELECT video_id, title, description, thumbnail, channel FROM videos")
    rows = cursor.fetchall()
    query_embedding = embed_text(query)
    videos = []

    for row in rows:
        video_id, title, desc, thumb, channel = row
        full_text = f"{title} {desc}"
        score = cosine_similarity(query_embedding, embed_text(full_text))

        if score > 0.4:
            videos.append({
                "video_id": video_id,
                "title": title,
                "description": desc,
                "thumbnail": thumb,
                "channel": channel,
                "link": f"https://www.youtube.com/watch?v={video_id}",
                "score": float(score)
            })

    # Fallback if no relevant results in DB
    if not videos:
        print("⚠️ No relevant results in DB — trying YouTube fallback...")
        yt_results = yt_fetch_videos(query, max_results=10)
        video_ids = [item["id"]["videoId"] for item in yt_results if "videoId" in item["id"]]

        if video_ids:
            video_details = get_video_details(video_ids)
            for video in video_details:
                insert_video(conn, video, subject="Auto", difficulty="Medium")

            for video in video_details:
                title = video["snippet"]["title"]
                desc = video["snippet"]["description"]
                score = cosine_similarity(query_embedding, embed_text(f"{title} {desc}"))

                videos.append({
                    "video_id": video["id"],
                    "title": title,
                    "description": desc,
                    "thumbnail": video["snippet"]["thumbnails"]["high"]["url"],
                    "channel": video["snippet"]["channelTitle"],
                    "link": f"https://www.youtube.com/watch?v={video['id']}",
                    "score": float(score)
                })

            print(f" Fallback results found and added: {len(videos)}")

        else:
            print(" No videos found via fallback.")


    conn.close()
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
    results = recommend("Thermodynamics", top_n=10, user_id="test_user")
    for video in results:
        print(f"Title: {video['title']}")
        print(f"Channel: {video['channel']}")
        print(f"Score: {video['score']:.4f}")
        print(f"Link: {video['link']}")
        print()
