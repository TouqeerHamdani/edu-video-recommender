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
    return response.json().get('items', [])

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

def main():
    conn = get_connection()
    search_results = fetch_videos("Class 10 Science", max_results=10)
    video_ids = [item['id']['videoId'] for item in search_results]

    detailed_videos = get_video_details(video_ids)
    for video in detailed_videos:
        insert_video(conn, video)

    conn.close()
    print("Videos inserted into the database.")

if __name__ == "__main__":
    main()
