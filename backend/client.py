import os
from typing import Optional

from supabase import Client, create_client

_url: Optional[str] = os.environ.get("supabaseurl")
_key: Optional[str] = os.environ.get("supabasekey")

if not _url or not _key:
    raise ValueError("supabaseurl and supabasekey environment variables must be set")

supabase: Client = create_client(_url, _key)
