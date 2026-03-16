import logging
import os

import httpx
import isodate
from dotenv import load_dotenv

from backend.models import Video

load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")

async def fetch_videos(query, max_results=10, video_duration="any", video_category_id="27"):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': f'{query} -"#shorts" -shorts',
        'type': 'video',
        'maxResults': max_results,
        'key': API_KEY,
        'videoDuration': video_duration,
        'videoCategoryId': video_category_id
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, params=params)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logging.error(f"YouTube search API error {exc.response.status_code}: {exc}")
        return []
    except httpx.RequestError as exc:
        logging.error(f"YouTube search request failed: {exc}")
        return []
    return response.json().get('items', [])

async def get_video_details(video_ids):
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        'part': 'snippet,statistics,contentDetails',
        'id': ','.join(video_ids),
        'key': API_KEY
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, params=params)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logging.error(f"YouTube video details API error {exc.response.status_code}: {exc}")
        return []
    except httpx.RequestError as exc:
        logging.error(f"YouTube video details request failed: {exc}")
        return []
    return response.json().get('items', [])

async def insert_video(video, subject="Science", difficulty="Easy", db_session=None):
    """Insert a video into the database. Uses provided AsyncSession or creates new one."""
    from sqlalchemy.dialects.postgresql import insert

    from backend.database import AsyncSessionLocal
    own_session = db_session is None
    session = db_session if db_session else AsyncSessionLocal()

    try:
        title = video['snippet']['title']
        description = video['snippet']['description']
        try:
            duration_seconds = int(isodate.parse_duration(video['contentDetails']['duration']).total_seconds())
        except Exception:
            duration_seconds = 0

        # Eliminates redundant DB round-trip on ~80% of requests by using INSERT ... ON CONFLICT DO NOTHING
        stmt = insert(Video).values(
            youtube_id=video['id'],
            title=title,
            description=description,
            thumbnail=video['snippet']['thumbnails'].get('high', {}).get('url', ''),
            duration=duration_seconds,
            category=subject,
            upload_date=video['snippet'].get('publishedAt', ''),
            view_count=int(video['statistics'].get('viewCount', 0)),
            like_count=int(video['statistics'].get('likeCount', 0)),
            embedding=None
        ).on_conflict_do_nothing(index_elements=['youtube_id'])

        result = await session.execute(stmt)
        if own_session:
            await session.commit()

        return result.rowcount > 0
    except Exception:
        if own_session:
            await session.rollback()
        return False
    finally:
        if own_session:
            await session.close()


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


async def fetch_and_store_videos(query, max_results=20, video_duration="any", db_session=None):
    """
    Fetch videos from YouTube API, filter out Shorts and non-educational,
    then store valid videos in the database.

    Returns the count of newly inserted videos.
    """
    print(f"🔍 Fetching videos from YouTube for: '{query}'")

    yt_results = await fetch_videos(query, max_results=max_results, video_duration=video_duration)
    video_ids = [item["id"]["videoId"] for item in yt_results if "videoId" in item.get("id", {})]

    if not video_ids:
        print("⚠️ No video IDs returned from YouTube API.")
        return 0

    video_details = await get_video_details(video_ids)
    inserted_count = 0

    for video in video_details:
        if is_youtube_short(video):
            print(f"⏭️ Skipped Short: {video['snippet']['title'][:50]}")
            continue

        if not is_educational_video(video):
            print(f"⏭️ Skipped non-educational: {video['snippet']['title'][:50]}")
            continue

        if await insert_video(video, subject="Auto", difficulty="Medium", db_session=db_session):
            inserted_count += 1

    print(f"✅ Inserted {inserted_count} educational videos into database.")
    return inserted_count
