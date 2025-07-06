import schedule
import time
from scraper.youtube_scraper import fetch_videos, get_video_details, insert_video
from scraper.db import get_connection
from scraper.semantic_search import embed_text

POPULAR_QUERIES = [
    "CBSE class 10 chemistry",
    "CBSE class 12 physics",
    "History of India",
    "Photosynthesis",
    "D and F block elements"
]

def run_scraper_job():
    print("🚀 Running background scrape...")

    conn = get_connection()

    for query in POPULAR_QUERIES:
        print(f"🔍 Scraping: {query}")
        try:
            results = fetch_videos(query, max_results=10)
            video_ids = [item['id']['videoId'] for item in results if 'videoId' in item['id']]
            videos = get_video_details(video_ids)

            for video in videos:
                insert_video(conn, video, subject="Auto", difficulty="Medium")
        except Exception as e:
            print(f"❌ Error during scraping {query}: {e}")

    conn.close()
    print("✅ Background scraping complete.\n")

# Run once immediately
run_scraper_job()

# Run job every hour (you can change this)
schedule.every(1).hours.do(run_scraper_job)

# Main loop
while True:
    schedule.run_pending()
    time.sleep(60)
