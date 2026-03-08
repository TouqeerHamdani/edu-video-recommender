import re

with open('backend/app.py', 'r') as f:
    content = f.read()

# Add BackgroundTasks to fastapi imports
if 'BackgroundTasks,' not in content and 'BackgroundTasks' not in content:
    content = content.replace('from fastapi import Depends, FastAPI, HTTPException, Request, status',
                              'from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status')

# Update get_recommendations definition
old_def = """async def get_recommendations(
    query: str,
    duration: str = "any",
    current_user: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db)
):"""

new_def = """async def get_recommendations(
    query: str,
    background_tasks: BackgroundTasks,
    duration: str = "any",
    current_user: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db)
):"""

content = content.replace(old_def, new_def)

# Find the await recommend(...) call and replace with background task scheduling logic
old_recommend_call = """        results = await recommend(query, top_n=10, user_id=current_user, video_duration=duration, db_session=db)

        # Convert dict results to Pydantic models
        valid_results = []
        for r in results:
            # Ensure safety if keys missing
            valid_results.append(VideoResult(**r))

        return RecommendationResponse(results=valid_results)"""

new_recommend_call = """        results = await recommend(query, top_n=10, user_id=current_user, video_duration=duration, db_session=db)

        # Convert dict results to Pydantic models
        valid_results = []
        for r in results:
            # Ensure safety if keys missing
            valid_results.append(VideoResult(**r))

        # Schedule background ingestion if we didn't find enough results
        if len(valid_results) < 10:
            from scraper.youtube_scraper import fetch_and_store_videos
            # We can't pass the same db_session to the background task because it will be closed
            # when the request completes. Passing None will tell fetch_and_store_videos to create its own.
            background_tasks.add_task(fetch_and_store_videos, query, 20, duration, None)

        return RecommendationResponse(results=valid_results)"""

content = content.replace(old_recommend_call, new_recommend_call)

with open('backend/app.py', 'w') as f:
    f.write(content)
