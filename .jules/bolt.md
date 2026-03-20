
## 2025-05-15 - [Database Performance] Use atomic insert for video deduplication
**Vulnerability/Bottleneck:** The scraper previously executed a `SELECT` query for every video to check for duplicates before `INSERT`, effectively doubling the database round-trips for the background insertion task.
**Learning:** For high-throughput scenarios (like background ingestion via `youtube_scraper.py`), `sqlalchemy.dialects.postgresql.insert` with `.on_conflict_do_nothing(index_elements=...)` is essential to minimize latency, particularly on unique constraints like `youtube_id`.
**Prevention:** Avoid pre-insert existence checks via `SELECT` when atomic upsert/ignore mechanisms exist.
