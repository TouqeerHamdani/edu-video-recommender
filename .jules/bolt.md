## 2024-06-18 - Replacing `SELECT` before `INSERT` with `INSERT ... ON CONFLICT DO NOTHING`

**Optimization:** Replaced the pattern of checking for video existence with `SELECT` before inserting with `INSERT ... ON CONFLICT DO NOTHING` in `scraper/youtube_scraper.py`.
**Learning:** This codebase relies heavily on unique constraints (`youtube_id`). The ORM-style full-object check (`select(Video)`) followed by an insert creates an N+1 round-trip bottleneck. By directly invoking `sqlalchemy.dialects.postgresql.insert` and utilizing `.on_conflict_do_nothing(index_elements=['youtube_id'])`, we can rely directly on the database to handle uniqueness in a single round-trip, yielding a massive win for bulk insertions from the scraper and eliminating the pre-insert check. This reduces DB query cost significantly and speeds up scraper throughput without breaking existing async session logic.
**Measurement:** Replaced 2 queries per insert check with 1 query.
