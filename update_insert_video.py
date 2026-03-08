
with open("scraper/youtube_scraper.py", "r") as f:
    content = f.read()

# Replace the insert_video function
old_insert_video = """async def insert_video(video, subject="Science", difficulty="Easy", db_session=None):
    \"\"\"Insert a video into the database. Uses provided AsyncSession or creates new one.\"\"\"
    from sqlalchemy import select
    from backend.database import AsyncSessionLocal
    own_session = db_session is None
    session = db_session if db_session else AsyncSessionLocal()

    try:
        title = video['snippet']['title']
        description = video['snippet']['description']
        try:
            duration_seconds = int(isodate.parse_duration(video['contentDetails']['duration']).total_seconds())
        except:
            duration_seconds = 0

        result = await session.execute(select(Video).filter(Video.youtube_id == video['id']))
        if result.scalars().first():
            if own_session:
                await session.close()
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
            embedding=None
        )
        session.add(video_record)
        if own_session:
            await session.commit()
        return True
    except Exception:
        if own_session:
            await session.rollback()
        return False
    finally:
        if own_session:
            await session.close()"""

new_insert_video = """async def insert_video(video, subject="Science", difficulty="Easy", db_session=None):
    \"\"\"Insert a video into the database. Uses provided AsyncSession or creates new one.\"\"\"
    from sqlalchemy.dialects.postgresql import insert
    from backend.database import AsyncSessionLocal
    own_session = db_session is None
    session = db_session if db_session else AsyncSessionLocal()

    try:
        title = video['snippet']['title']
        description = video['snippet']['description']
        try:
            duration_seconds = int(isodate.parse_duration(video['contentDetails']['duration']).total_seconds())
        except:
            duration_seconds = 0

        # Avoids a SELECT before INSERT by using ON CONFLICT DO NOTHING
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
    except Exception as e:
        logging.error(f"Failed to insert video: {e}")
        if own_session:
            await session.rollback()
        return False
    finally:
        if own_session:
            await session.close()"""

if old_insert_video in content:
    content = content.replace(old_insert_video, new_insert_video)
    with open("scraper/youtube_scraper.py", "w") as f:
        f.write(content)
    print("Successfully replaced insert_video")
else:
    print("Could not find old_insert_video in file")
