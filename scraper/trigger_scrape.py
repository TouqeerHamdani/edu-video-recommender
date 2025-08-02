import os
import logging
from scraper.tasks import scrape_and_store
from scraper.dynamic_queries import get_top_user_queries

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get top user queries dynamically
query_list = get_top_user_queries(limit=10, days=7)

# Prevent duplicate scheduling using a simple set (could be replaced with Redis/db for distributed systems)
scheduled_queries = set()

for query in query_list:
    if query in scheduled_queries:
        continue
    try:
        scrape_and_store.delay(query)
        scheduled_queries.add(query)
    except Exception as e:
        print(f"Failed to schedule scraping for query: {query}, error: {e}")
