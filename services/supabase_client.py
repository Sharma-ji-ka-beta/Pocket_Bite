import os
from functools import lru_cache

from supabase import create_client


@lru_cache(maxsize=1)
def get_supabase_client():
    """
    Create a single Supabase client instance for the process.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_KEY environment variables."
        )

    return create_client(supabase_url, supabase_key)

