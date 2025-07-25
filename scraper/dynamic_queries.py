from scraper.db import get_connection

def get_top_user_queries(limit=10, days=7):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT query, COUNT(*) as freq
            FROM user_searches
            WHERE search_time > NOW() - INTERVAL '%s days'
            GROUP BY query
            ORDER BY freq DESC, MAX(search_time) DESC
            LIMIT %s
        """, (days, limit))
        queries = [row[0] for row in cur.fetchall()]
    conn.close()
    return queries 