import numpy as np
from sentence_transformers import SentenceTransformer
from scraper.db import get_connection
conn = get_connection()
print("✅ Database connection successful!")
conn.close()

# Load model once
model = SentenceTransformer('all-MiniLM-L6-v2')

def fetch_videos():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT video_id, title, description, channel, thumbnail FROM videos")
        rows = cur.fetchall()
    conn.close()
    return [
        {
            'video_id': row[0],
            'title': row[1],
            'description': row[2],
            'channel': row[3],
            'thumbnail': row[4]
        }
        for row in rows
    ]

def embed_text(text):
    return model.encode(text, convert_to_numpy=True)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def recommend(query, top_n=5):
    query_embedding = embed_text(query)
    videos = fetch_videos()

    print(f"Fetched {len(videos)} videos from DB")  # <== ADD THIS LINE

    for video in videos:
        combined_text = f"{video['title']} {video['description']}"
        video['embedding'] = embed_text(combined_text)
        video['score'] = cosine_similarity(query_embedding, video['embedding'])

    sorted_videos = sorted(videos, key=lambda x: x['score'], reverse=True)
    cleaned = []
    for video in sorted_videos[:top_n]:
        cleaned.append({
            "title": video["title"],
            "channel": video["channel"],
            "score": round(float(video["score"]), 4),
            "link": f"https://www.youtube.com/watch?v={video['video_id']}",
            "thumbnail": video["thumbnail"]
        })
    return cleaned
def log_search(query, user_id="guest"):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO user_searches (user_id, query) VALUES (%s, %s)",
            (user_id, query)
        )
        conn.commit()
    conn.close()

if __name__ == "__main__":
    results = recommend("Class 10 Science chapter 1")
    for video in results:
        print(f"Title: {video['title']}")
        print(f"Channel: {video['channel']}")
        print(f"Score: {video['score']:.4f}")
        print(f"Link: https://www.youtube.com/watch?v={video['video_id']}")
        print()
