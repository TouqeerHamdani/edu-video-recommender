## 2024-03-14 - Replace Pre-Insert SELECT with INSERT ... ON CONFLICT DO NOTHING
**Vulnerability/Bottleneck:** The `insert_video` function currently runs a `SELECT` query to check if a video exists before inserting it. This creates a redundant DB round-trip for every video fetched.
**Learning:** Using `INSERT ... ON CONFLICT DO NOTHING` via `sqlalchemy.dialects.postgresql.insert` eliminates this extra `SELECT` overhead, improving throughput when batching or fetching new videos.
**Prevention:** Default to atomic insert operations leveraging database constraints rather than application-side checks.
