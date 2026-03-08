import re
import sys

with open('scraper/semantic_search.py', 'r') as f:
    content = f.read()

# Replace _execute_text_search with our new _execute_hybrid_search
new_execute_hybrid_search = '''
async def _execute_hybrid_search(session, query, embedding_list, duration_filter_sql, limit):
    """
    Run a hybrid search combining Semantic (pgvector), Keyword (pg_trgm + FTS), and Fuzzy matching
    using Reciprocal Rank Fusion (RRF).
    """
    # If no embedding is available, fallback to only FTS and Fuzzy
    if embedding_list is None:
        sql = f"""
        WITH keyword_search AS (
            SELECT id,
                   ts_rank(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')),
                           websearch_to_tsquery('english', :query)) as rank_score
            FROM videos
            WHERE to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))
                  @@ websearch_to_tsquery('english', :query) {duration_filter_sql}
        ),
        fuzzy_search AS (
            SELECT id,
                   similarity(coalesce(title, '') || ' ' || coalesce(description, ''), :query) as rank_score
            FROM videos
            WHERE coalesce(title, '') || ' ' || coalesce(description, '') % :query {duration_filter_sql}
        ),
        keyword_ranked AS (
            SELECT id, row_number() OVER (ORDER BY rank_score DESC) as rank_pos FROM keyword_search
        ),
        fuzzy_ranked AS (
            SELECT id, row_number() OVER (ORDER BY rank_score DESC) as rank_pos FROM fuzzy_search
        ),
        rrf_scores AS (
            SELECT COALESCE(k.id, f.id) as id,
                   COALESCE(1.0 / (60 + k.rank_pos), 0.0) +
                   COALESCE(1.0 / (60 + f.rank_pos), 0.0) as rrf_score
            FROM keyword_ranked k
            FULL OUTER JOIN fuzzy_ranked f ON k.id = f.id
        )
        SELECT v.youtube_id, v.title, v.description, v.thumbnail, v.duration, v.view_count, v.like_count, r.rrf_score as similarity_score
        FROM rrf_scores r
        JOIN videos v ON r.id = v.id
        ORDER BY r.rrf_score DESC
        LIMIT :limit
        """
        params = {"query": query, "limit": limit}
    else:
        sql = f"""
        WITH semantic_search AS (
            SELECT id,
                   1 - (embedding <=> :query_embedding) as rank_score
            FROM videos
            WHERE embedding IS NOT NULL AND 1 - (embedding <=> :query_embedding) > 0.3 {duration_filter_sql}
        ),
        keyword_search AS (
            SELECT id,
                   ts_rank(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')),
                           websearch_to_tsquery('english', :query)) as rank_score
            FROM videos
            WHERE to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))
                  @@ websearch_to_tsquery('english', :query) {duration_filter_sql}
        ),
        fuzzy_search AS (
            SELECT id,
                   similarity(coalesce(title, '') || ' ' || coalesce(description, ''), :query) as rank_score
            FROM videos
            WHERE coalesce(title, '') || ' ' || coalesce(description, '') % :query {duration_filter_sql}
        ),
        semantic_ranked AS (
            SELECT id, row_number() OVER (ORDER BY rank_score DESC) as rank_pos FROM semantic_search
        ),
        keyword_ranked AS (
            SELECT id, row_number() OVER (ORDER BY rank_score DESC) as rank_pos FROM keyword_search
        ),
        fuzzy_ranked AS (
            SELECT id, row_number() OVER (ORDER BY rank_score DESC) as rank_pos FROM fuzzy_search
        ),
        rrf_scores AS (
            SELECT COALESCE(s.id, COALESCE(k.id, f.id)) as id,
                   COALESCE(1.0 / (60 + s.rank_pos), 0.0) +
                   COALESCE(1.0 / (60 + k.rank_pos), 0.0) +
                   COALESCE(1.0 / (60 + f.rank_pos), 0.0) as rrf_score
            FROM semantic_ranked s
            FULL OUTER JOIN keyword_ranked k ON s.id = k.id
            FULL OUTER JOIN fuzzy_ranked f ON COALESCE(s.id, k.id) = f.id
        )
        SELECT v.youtube_id, v.title, v.description, v.thumbnail, v.duration, v.view_count, v.like_count, r.rrf_score as similarity_score
        FROM rrf_scores r
        JOIN videos v ON r.id = v.id
        ORDER BY r.rrf_score DESC
        LIMIT :limit
        """
        params = {"query": query, "query_embedding": str(embedding_list), "limit": limit}

    return await session.execute(text(sql), params)
'''

# First, replace the old _execute_text_search definition
content = re.sub(
    r'async def _execute_text_search.*?return await session\.execute\(\s*text\(sql\),\s*\{"query": query, "limit": limit\}\s*\)',
    new_execute_hybrid_search.strip(),
    content,
    flags=re.DOTALL
)

# Second, refactor recommend to use the new hybrid search
# Find where recommend starts
recommend_start = content.find('async def recommend(')
if recommend_start == -1:
    print("Could not find recommend()")
    sys.exit(1)

recommend_prefix = content[:recommend_start]

new_recommend = '''async def recommend(query, top_n=5, user_id="guest", video_duration="any", db_session=None):
    own_session = False
    if db_session:
        session = db_session
    else:
        session = _get_local_async_session()
        own_session = True

    try:
        print(f"Searching for: '{query}' (duration: {video_duration})")
        start_time = time.time()

        # === STEP 1: Build duration filter + generate query embedding ===
        from scraper.youtube_scraper import fetch_and_store_videos

        # Build duration filter
        duration_filter_sql = ""
        if video_duration == "short":
            duration_filter_sql = "AND duration < 240"  # < 4 minutes
        elif video_duration == "medium":
            duration_filter_sql = "AND duration >= 240 AND duration < 1200"  # 4-20 minutes
        elif video_duration == "long":
            duration_filter_sql = "AND duration >= 1200"  # >= 20 minutes

        # Cached after first request — no DB round-trip on subsequent calls (report §3.3)
        has_any_embeddings = await _check_has_embeddings(session)

        query_vector = None
        embedding_list = None
        if has_any_embeddings:
            query_vector = await create_query_embedding(query)
            if query_vector is not None:
                embedding_list = query_vector.tolist() if hasattr(query_vector, 'tolist') else query_vector
        else:
            print("⏭️ Skipping embedding — no embedded videos exist in DB")

        # === STEP 2: Execute Hybrid RRF Search ===
        print("Executing Hybrid Search (Vector + FTS + Fuzzy) using Reciprocal Rank Fusion...")
        result = await _execute_hybrid_search(session, query, embedding_list, duration_filter_sql, top_n)
        rows = result.fetchall()

        videos = []
        seen_ids = set()

        # Process the hybrid results
        _process_text_rows(rows, seen_ids, videos, base_score=None) # We use None so _process_text_rows uses popularity logic, but wait, we should pass similarity_score instead of popularity.

        # Actually _process_text_rows doesn't use the similarity score correctly, so let's process manually
        videos = []
        for row in rows:
            youtube_id, title, description, thumbnail, duration, view_count, like_count, similarity = row
            view_count = view_count or 0
            like_count = like_count or 0

            # Blend RRF score with popularity
            views_norm = min(view_count / 1000000, 1.0) # Cap at 1M
            likes_norm = min(like_count / 50000, 1.0) # Cap at 50k
            popularity = 0.5 * views_norm + 0.5 * likes_norm
            final_score = (similarity * 0.7) + (popularity * 0.3)

            videos.append({
                "video_id": youtube_id,
                "title": title,
                "description": description,
                "thumbnail": thumbnail,
                "channel": "YouTube",
                "link": f"https://www.youtube.com/watch?v={youtube_id}",
                "score": final_score,
                "views": view_count,
                "likes": like_count
            })

        videos = sorted(videos, key=lambda v: v["score"], reverse=True)

        # === STEP 3: Return immediately, caller handles background ingestion ===
        if own_session:
            await session.close()

        elapsed_time = time.time() - start_time
        print(f"Hybrid Search completed in {elapsed_time:.2f} seconds. Found {len(videos)} videos.")

        return videos[:top_n]

    except Exception as e:
        print(f"[ERROR] Recommend failed: {e}")
        if own_session:
            await session.close()
        return []
'''

# Find where log_search starts
log_search_start = content.find('async def log_search(')
if log_search_start == -1:
    print("Could not find log_search()")
    sys.exit(1)

content = recommend_prefix + new_recommend + "\n" + content[log_search_start:]

with open('scraper/semantic_search.py', 'w') as f:
    f.write(content)
