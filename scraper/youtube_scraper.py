import os

import isodate
import requests
from dotenv import load_dotenv

from backend.database import get_session
from backend.models import Video

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
        'videoDuration': video_duration,
        'videoCategoryId': video_category_id
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

def insert_video(video, subject="Science", difficulty="Easy", db_session=None):
    """Insert a video into the database. Uses provided session or creates new one."""
    session = db_session if db_session else get_session()
    owns_session = db_session is None
    
    try:
        title = video['snippet']['title']
        description = video['snippet']['description']
        try:
            duration_seconds = int(isodate.parse_duration(video['contentDetails']['duration']).total_seconds())
        except:
            duration_seconds = 0

        existing = session.query(Video).filter(Video.youtube_id == video['id']).first()
        if existing:
            if owns_session:
                session.close()
            return False

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
            embedding=None  # Disabled for Phase 1
        )
        session.add(video_record)
        if owns_session:
            session.commit()
        return True
    except Exception:
        if owns_session:
            session.rollback()
        return False
    finally:
        if owns_session:
            session.close()


def is_youtube_short(video):
    """Returns True if video is a YouTube Short (duration < 60s or #shorts in title/desc)."""
    try:
        duration_seconds = int(isodate.parse_duration(video['contentDetails']['duration']).total_seconds())
    except Exception:
        return True  # Assume short if can't parse duration
    
    title = video['snippet'].get('title', '').lower()
    description = video['snippet'].get('description', '').lower()
    
    return duration_seconds < 60 or '#shorts' in title or '#shorts' in description


def is_educational_video(video):
    """Returns True if video is in the Education category (27)."""
    category_id = video['snippet'].get('categoryId', '')
    return category_id == '27'


def fetch_and_store_videos(query, max_results=20, video_duration="medium", db_session=None):
    """
    Fetch videos from YouTube API, filter out Shorts and non-educational,
    then store valid videos in the database.
    
    Returns the count of newly inserted videos.
    """
    print(f"🔍 Fetching videos from YouTube for: '{query}'")
    
    # Fetch from YouTube (already filters by category 27 and duration)
    yt_results = fetch_videos(query, max_results=max_results, video_duration=video_duration)
    video_ids = [item["id"]["videoId"] for item in yt_results if "videoId" in item.get("id", {})]
    
    if not video_ids:
        print("⚠️ No video IDs returned from YouTube API.")
        return 0
    
    # Get full video details
    video_details = get_video_details(video_ids)
    inserted_count = 0
    
    for video in video_details:
        # Skip YouTube Shorts
        if is_youtube_short(video):
            print(f"⏭️ Skipped Short: {video['snippet']['title'][:50]}")
            continue
        
        # Skip non-educational videos
        if not is_educational_video(video):
            print(f"⏭️ Skipped non-educational: {video['snippet']['title'][:50]}")
            continue
        
        # Insert valid video
        if insert_video(video, subject="Auto", difficulty="Medium", db_session=db_session):
            inserted_count += 1
    
    print(f"✅ Inserted {inserted_count} educational videos into database.")
    return inserted_count

