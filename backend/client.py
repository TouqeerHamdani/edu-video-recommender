import os
from typing import Optional

from supabase import Client, create_client

_url: Optional[str] = os.environ.get("supabaseurl")
_key: Optional[str] = os.environ.get("supabasekey")

if _url and _key:
    supabase: Client = create_client(_url, _key)
else:
    # Allow import without credentials (e.g. in tests that mock supabase).
    # Any real call to supabase will fail fast with an AttributeError, which
    # is caught and re-raised by the auth layer.
    supabase = None  # type: ignore[assignment]
