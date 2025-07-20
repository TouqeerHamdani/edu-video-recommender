import os
import logging
from scraper.tasks import scrape_and_store

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load queries from environment variable or a config file
# Example: EDU_QUERIES="class 10 science,cbse class 12 chemistry,ncert physics electricity"
queries = os.getenv("EDU_QUERIES")
if queries:
    query_list = [q.strip() for q in queries.split(",") if q.strip()]
else:
    # Fallback to default queries if env variable not set
    query_list = [
        "class 10 science",
        "cbse class 12 chemistry",
        "ncert physics electricity"
    ]

# Prevent duplicate scheduling using a simple set (could be replaced with Redis/db for distributed systems)
scheduled_queries = set()

for query in query_list:
    if query in scheduled_queries:
        logger.warning(f"Duplicate query detected, skipping: {query}")
        continue
    try:
        scrape_and_store.delay(query)
        logger.info(f"Scheduled scraping task for query: {query}")
        scheduled_queries.add(query)
    except Exception as e:
        logger.error(f"Failed to schedule scraping for query: {query}, error: {e}")
