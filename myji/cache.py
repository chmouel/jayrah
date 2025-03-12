import hashlib
import json
import os
import time
from pathlib import Path


class JiraCache:
    """Cache handler for Jira API responses"""

    def __init__(self, cache_dir=None, cache_ttl=3600):
        """
        Initialize the cache handler

        Args:
            cache_dir (str): Directory to store cache files (defaults to ~/.cache/myji/)
            cache_ttl (int): Time to live for cache entries in seconds (default: 1 hour)
        """
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.cache/myji")

        self.cache_dir = Path(cache_dir)
        self.cache_ttl = cache_ttl

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, url, params=None, json_data=None):
        """Generate a cache key from request details"""
        key_parts = [url]

        if params:
            key_parts.append(str(sorted(params.items())))

        if json_data:
            key_parts.append(
                str(
                    sorted(json_data.items())
                    if isinstance(json_data, dict)
                    else json_data
                )
            )

        key_string = "".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_cache_path(self, cache_key):
        """Get the file path for a cache key"""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, url, params=None, json_data=None):
        """
        Get a cached response if available and not expired

        Returns:
            dict: The cached response or None if not found/expired
        """
        cache_key = self._get_cache_key(url, params, json_data)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                cached_data = json.load(f)

            # Check if cache has expired
            if time.time() - cached_data["timestamp"] > self.cache_ttl:
                return None

            return cached_data["data"]
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            # Invalid or corrupt cache
            return None

    def set(self, url, response_data, params=None, json_data=None):
        """Save response data to cache"""
        cache_key = self._get_cache_key(url, params, json_data)
        cache_path = self._get_cache_path(cache_key)

        cached_data = {"timestamp": time.time(), "data": response_data}

        with open(cache_path, "w") as f:
            json.dump(cached_data, f)

    def clear(self):
        """Clear all cached data"""
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except OSError:
                pass
