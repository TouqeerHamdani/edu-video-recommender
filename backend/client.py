import os

from supabase import Client, create_client

from typing import Optional

_url: Optional[str] = os.environ.get("supabaseurl")
_key: Optional[str] = os.environ.get("supabasekey")

if not _url or not _key:
    raise ValueError("supabaseurl and supabasekey environment variables must be set")

supabase: Client = create_client(_url, _key)
