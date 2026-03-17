## 2025-05-14 - [Performance] Eliminating Pre-Insert SELECTs
**Bottleneck:** In `insert_video()`, a `SELECT` query is executed before every `INSERT` to check for duplicates, adding unnecessary database round-trips.
**Learning:** PostgreSQL's `INSERT ... ON CONFLICT DO NOTHING` via `sqlalchemy.dialects.postgresql.insert` can handle duplicate prevention efficiently on the database side, eliminating the N+1 query pattern during video batch ingestion.
**Prevention:** Default to using upsert/conflict semantics instead of application-level uniqueness checks when ingesting external data.
