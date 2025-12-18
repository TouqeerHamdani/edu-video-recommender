import os
import requests
from dotenv import load_dotenv
from backend.database import get_session
from backend.models import Video
#from scraper.semantic_utils import embed_text
import isodate

load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")

def fetch_videos(query, max_results=10, video_duration="medium", video_category_id="27"):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': query,
        'type': 'video',
        'maxResults': max_results,
        'key': API_KEY,
        'videoDuration': video_duration,  # 'any', 'short', 'medium', 'long'
        'videoCategoryId': video_category_id  # '27' for Education
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

def insert_video(video, subject="Science", difficulty="Easy"):
    """Insert video using SQLAlchemy ORM."""
    session = get_session()
    try:
        title = video['snippet']['title']
        description = video['snippet']['description']
        full_text = f"{title} {description}"
        embedding = embed_text(full_text)

        if embedding is None:
            print(f"Failed to embed video {video['id']}")
            return

        # Parse duration to seconds
        try:
            duration_seconds = int(isodate.parse_duration(video['contentDetails']['duration']).total_seconds())
        except:
            duration_seconds = 0

        # Check if video already exists
        existing = session.query(Video).filter(Video.youtube_id == video['id']).first()
        if existing:
            session.close()
            return  # Skip duplicate

        # Create new video record
        video_record = Video(
            youtube_id=video['id'],
            title=title,
            description=description,
            thumbnail=video['snippet']['thumbnails'].get('high', {}).get('url', ''),
            duration=duration_seconds,
            category=subject,
            upload_date=video['snippet'].get('publishedAt', ''),
            view_count=int(video['statistics'].get('viewCount', 0)),
            like_count=int(video['statistics'].get('likeCount', 0)),
            embedding=embedding.tolist()
        )

        session.add(video_record)
        session.commit()
        print(f"Inserted video: {title[:50]}...")

    except Exception as e:
        print(f"Error inserting video {video['id']}: {e}")
        session.rollback()
    finally:
        session.close()


def main():
    if not API_KEY:
        print(" API Key is missing — check your .env file.")
        return

    # Try a broader query
    search_query = "organic chemistry "  # Try "Class 10", "Math", etc.
    search_results = fetch_videos(search_query, max_results=100)

    # DEBUG 2: Print full API response
    print(" Full API Response:")
    print(search_results)

    video_ids = [item['id']['videoId'] for item in search_results if 'videoId' in item['id']]
    print("Video IDs found:", video_ids)

    if not video_ids:
        print(" No video IDs found from search results.")
        return

    detailed_videos = get_video_details(video_ids)

    for video in detailed_videos:
        try:
            insert_video(video)

        except Exception as e:
            print(f" Error inserting video {video['id']}: {e}")

    print(" Done inserting videos.")


if __name__ == "__main__":
    main()
