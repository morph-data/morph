from datetime import datetime, timedelta
from typing import List


class ExecutionCache:
    """
    A class to maintain TTL-based caching of run results.
    If expiration_seconds == 0, caching is disabled (no cache entries are stored or retrieved).
    """

    def __init__(self, expiration_seconds: int = 0):
        """
        Initialize the execution cache.

        :param expiration_seconds: The number of seconds after which a cache entry expires.
                                   If set to 0, caching is disabled.
        """
        self.cache: dict[str, dict[str, object]] = {}
        self.expiration_seconds = expiration_seconds

    def update_cache(self, function_name: str, cache_paths: List[str]) -> None:
        """
        Update or add an entry to the cache. Replaces existing cache paths with the provided ones.
        If expiration_seconds == 0, do nothing (caching is disabled).
        """
        if self.expiration_seconds == 0:
            return  # Skip storing anything

        current_time = datetime.now().isoformat()
        cache_entry = self.cache.get(function_name)

        # Check if an existing cache entry is still valid
        if cache_entry:
            last_executed_at = cache_entry.get("last_executed_at")
            if isinstance(last_executed_at, str):
                last_executed_time = datetime.fromisoformat(last_executed_at)
                if datetime.now() - last_executed_time <= timedelta(
                    seconds=self.expiration_seconds
                ):
                    # Cache is still valid, only update the cache paths
                    cache_entry["cache_paths"] = cache_paths
                    return

        # Either no cache entry exists, or the cache has expired
        self.cache[function_name] = {
            "last_executed_at": current_time,
            "cache_paths": cache_paths,
        }

    def clear_cache(self, function_name: str) -> None:
        """
        Remove the cache entry for a specific function.
        """
        if function_name in self.cache:
            del self.cache[function_name]

    def clear_all_cache(self) -> None:
        """
        Clear all cache entries.
        """
        self.cache.clear()

    def list_all_cache(self) -> List[str]:
        """
        List all function names currently cached.
        """
        return list(self.cache.keys())
