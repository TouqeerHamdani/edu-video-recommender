from celery_app import celery
from scraper.background_scraper import run_scraper

@celery.task
def scrape_and_store(query="class 10 science", max_results=50):
    run_scraper(query, max_results)
