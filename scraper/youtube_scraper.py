import os
import requests
from dotenv import load_dotenv
from backend.database import get_session
from backend.models import Video
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

def insert_video(video, subject="Science", difficulty="Easy"):
    session = get_session()
    try:
        title = video['snippet']['title']
        description = video['snippet']['description']
        try:
            duration_seconds = int(isodate.parse_duration(video['contentDetails']['duration']).total_seconds())
        except:
            duration_seconds = 0

        existing = session.query(Video).filter(Video.youtube_id == video['id']).first()
        if existing:
            session.close()
            return

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
        session.commit()
    except Exception as e:
        session.rollback()
    finally:
        session.close()
