from scraper.youtube_scraper import fetch_videos, get_video_details, insert_video
from scraper.db import get_connection

def run_scraper(query="class 10 science", max_results=50):
    print(f"🔍 Running background scraper for: '{query}'")

    yt_results = fetch_videos(query, max_results)
    video_ids = [item["id"]["videoId"] for item in yt_results if "videoId" in item["id"]]

    if not video_ids:
        print("⚠️ No video IDs returned from YouTube API.")
        return

    video_details = get_video_details(video_ids)
    conn = get_connection()
    inserted = 0

    for video in video_details:
        #  Only store educational videos
        if video["snippet"].get("categoryId") != "27":
            print(f" Skipped non-educational video: {video['snippet']['title']}")
            continue

        insert_video(conn, video, subject="Auto", difficulty="Medium")
        inserted += 1

    conn.close()
    print(f" Inserted {inserted} educational videos into the database.")

# Optional: Run manually
if __name__ == "__main__":
    run_scraper(query="cbse class 12 physics", max_results=25) 