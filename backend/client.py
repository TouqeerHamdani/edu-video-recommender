import os
from supabase import create_client, Client

url: str = os.environ.get("supabaseurl")
key: str = os.environ.get("supabasekey")

if not url or not key:
    raise ValueError("supabaseurl and supabasekey environment variables must be set")

supabase: Client = create_client(url, key)
