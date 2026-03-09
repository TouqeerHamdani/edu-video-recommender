## Bolt's Daily Process - Journal

*   **Optimization selected:** Replaced the two-step `SELECT` then `INSERT` process in `insert_video` (in `scraper/youtube_scraper.py`) with a single `INSERT ... ON CONFLICT DO NOTHING`.
*   **Bottleneck:** The scraper was doing a redundant database round-trip for every video it tried to process, slowing down batch ingestion and adding load to the database.
*   **Learning:** By using the PostgreSQL dialect's `insert()` statement and `.on_conflict_do_nothing()`, we can eliminate the need for an initial `SELECT` query, halving the database overhead during YouTube data scraping. Returning `result.rowcount > 0` cleanly preserves the original `True/False` return semantics for existing versus new videos.
