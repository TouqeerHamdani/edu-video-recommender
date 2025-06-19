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

def recommend(query, top_n=5, user_id="guest"):
    query_embedding = embed_text(query)
    user_profile = get_user_profile(user_id)

    videos = fetch_videos()
    recommendations = []

    for video in videos:
        combined_text = f"{video['title']} {video['description']}"
        video_embedding = embed_text(combined_text)

        # Main similarity: query vs video
        similarity = cosine_similarity(query_embedding, video_embedding)

        # Personalization: user profile vs video
        if user_profile is not None:
            personalization = cosine_similarity(user_profile, video_embedding)
            final_score = 0.7 * similarity + 0.3 * personalization
        else:
            final_score = similarity

        recommendations.append({
            "title": video["title"],
            "channel": video["channel"],
            "score": round(float(final_score), 4),
            "link": f"https://www.youtube.com/watch?v={video['video_id']}",
            "thumbnail": video["thumbnail"]
        })

    sorted_videos = sorted(recommendations, key=lambda x: x["score"], reverse=True)
    return sorted_videos[:top_n]


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
