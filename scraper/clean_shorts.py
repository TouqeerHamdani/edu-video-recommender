import isodate
from scraper.db import get_connection

def is_short(duration_iso, title, description):
    try:
        duration_seconds = isodate.parse_duration(duration_iso).total_seconds()
    except Exception:
        return True  # If can't parse, treat as short
    title = title.lower()
    description = description.lower()
    return duration_seconds < 60 or "#shorts" in title or "#shorts" in description

def clean_shorts():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT video_id, duration, title, description FROM videos")
    rows = cur.fetchall()
    to_delete = []
    for video_id, duration, title, description in rows:
        if is_short(duration, title, description):
            to_delete.append(video_id)
    print(f"Found {len(to_delete)} shorts to delete.")
    for vid in to_delete:
        cur.execute("DELETE FROM videos WHERE video_id = %s", (vid,))
    conn.commit()
    cur.close()
    conn.close()
    print("Deleted all shorts.")

if __name__ == "__main__":
    clean_shorts()