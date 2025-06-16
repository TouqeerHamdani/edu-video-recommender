import os
import requests
from dotenv import load_dotenv
from db import get_connection

load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")

def fetch_videos(query, max_results=10):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': query,
        'type': 'video',
        'maxResults': max_results,
        'key': API_KEY
    }

    response = requests.get(url, params=params)
    items = response.json().get('items', [])
    print(f"🔍 Search returned {len(items)} items.")
    return items

def get_video_details(video_ids):
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        'part': 'snippet,statistics,contentDetails',
        'id': ','.join(video_ids),
        'key': API_KEY
    }

    response = requests.get(url, params=params)
    return response.json().get('items', [])

def insert_video(conn, video):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO videos (
                video_id, title, description, channel, thumbnail,
                views, likes, duration, subject, difficulty
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id) DO NOTHING;
        """, (
            video['id'],
            video['snippet']['title'],
            video['snippet']['description'],
            video['snippet']['channelTitle'],
            video['snippet']['thumbnails']['high']['url'],
            int(video['statistics'].get('viewCount', 0)),
            int(video['statistics'].get('likeCount', 0)),
            video['contentDetails']['duration'],
            'Science',     # Default subject
            'Easy'         # Default difficulty
        ))
        conn.commit()
        print(f"✅ Inserted: {video['snippet']['title']}")

def main():
    conn = get_connection()

    # DEBUG 1: Check if API key is loaded
    print("🗝️ Using API Key:", API_KEY)
    if not API_KEY:
        print("❌ API Key is missing — check your .env file.")
        return

    # Try a broader query
    search_query = "Science"  # Try "Class 10", "Math", etc.
    search_results = fetch_videos(search_query, max_results=10)

    # DEBUG 2: Print full API response
    print("🔍 Full API Response:")
    print(search_results)

    video_ids = [item['id']['videoId'] for item in search_results if 'videoId' in item['id']]
    print("🎯 Video IDs found:", video_ids)

    if not video_ids:
        print("❌ No video IDs found from search results.")
        return

    detailed_videos = get_video_details(video_ids)

    for video in detailed_videos:
        try:
            insert_video(conn, video)
        except Exception as e:
            print(f"❌ Error inserting video {video['id']}: {e}")

    conn.close()
    print("🎉 Done inserting videos.")


if __name__ == "__main__":
    main()
