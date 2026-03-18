
## 2025-03-18 - [Performance] Use INSERT ... ON CONFLICT DO NOTHING for video insertion
**Vulnerability/Bottleneck:** `insert_video` in `scraper/youtube_scraper.py` executed a `SELECT` query followed by an `INSERT` to ensure no duplicates. This resulted in redundant database round-trips for every YouTube video fetched during a search query.
**Learning:** For batch insertion operations, particularly those occurring dynamically in response to user search requests in a FastAPI + PostgreSQL setup, `INSERT ... ON CONFLICT DO NOTHING` (via `sqlalchemy.dialects.postgresql.insert`) effectively eliminates the N+1 round-trip performance cost associated with checking unique constraints prior to insertion.
**Prevention:** Always leverage the database's native constraint resolution handling, rather than duplicating the verification in application logic, especially when using bulk remote fetches.
