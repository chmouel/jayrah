import hashlib
import json
import pickle
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional


class JiraCache:
    """Cache for Jira API requests."""

    def __init__(self, config):
        """Initialize the cache."""
        self.config = config
        self.cache_ttl = config.get("cache_ttl", 3600)  # Default: 1 hour

        # Create cache directory if it doesn't exist
        self.cache_dir = Path(
            config.get("cache_dir", Path.home() / ".cache" / "jayrah")
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # SQLite database for cache
        self.db_path = self.cache_dir / "cache.db"
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create cache table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                data BLOB,
                timestamp REAL
            )
        """)

        conn.commit()
        conn.close()

    def _get_connection(self):
        """Get a connection to the SQLite database."""
        return sqlite3.connect(self.db_path)

    def _generate_key(
        self, url: str, params: Optional[Dict] = None, data: Optional[Dict] = None
    ) -> str:
        """Generate a unique key for the cache entry."""
        # Create a string representation of the request
        key_parts = [url]

        if params:
            key_parts.append(json.dumps(params, sort_keys=True))

        if data:
            key_parts.append(json.dumps(data, sort_keys=True))

        key_str = "|".join(key_parts)

        # Generate a hash of the key string
        return hashlib.md5(key_str.encode("utf-8")).hexdigest()

    def get(
        self, url: str, params: Optional[Dict] = None, data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Get a cached response."""
        # If caching is disabled, return None
        if self.config.get("no_cache"):
            return None

        key = self._generate_key(url, params, data)

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get the cache entry
            cursor.execute("SELECT data, timestamp FROM cache WHERE key = ?", (key,))
            result = cursor.fetchone()
            conn.close()

            # If no cache entry, return None
            if not result:
                return None

            cached_data, timestamp = result

            # Check if the cache entry has expired
            if time.time() - timestamp > self.cache_ttl:
                self._remove_entry(key)
                return None

            # Deserialize the cached data
            return pickle.loads(cached_data)

        except (sqlite3.Error, pickle.PickleError) as e:
            print(f"Error retrieving from cache: {e}")
            return None

    def set(
        self,
        url: str,
        data: Any,
        params: Optional[Dict] = None,
        request_data: Optional[Dict] = None,
    ) -> None:
        """Set a cached response."""
        # If caching is disabled, do nothing
        if self.config.get("no_cache"):
            return

        key = self._generate_key(url, params, request_data)
        timestamp = time.time()

        try:
            # Serialize the data with pickle for better performance
            pickled_data = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)

            conn = self._get_connection()
            cursor = conn.cursor()

            # Insert or replace the cache entry
            cursor.execute(
                "INSERT OR REPLACE INTO cache (key, data, timestamp) VALUES (?, ?, ?)",
                (key, pickled_data, timestamp),
            )

            conn.commit()
            conn.close()

        except (sqlite3.Error, pickle.PickleError) as e:
            print(f"Error setting cache: {e}")

    def _remove_entry(self, key: str) -> None:
        """Remove a cache entry."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM cache WHERE key = ?", (key,))

            conn.commit()
            conn.close()

        except sqlite3.Error as e:
            print(f"Error removing cache entry: {e}")

    def clear(self) -> None:
        """Clear all cache entries."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM cache")

            conn.commit()
            conn.close()

        except sqlite3.Error as e:
            print(f"Error clearing cache: {e}")

    def prune(self, max_age: Optional[int] = None) -> int:
        """
        Remove expired cache entries.

        Args:
            max_age: Maximum age of cache entries in seconds (default: cache_ttl)

        Returns:
            Number of pruned entries
        """
        if max_age is None:
            max_age = self.cache_ttl

        cutoff_time = time.time() - max_age

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM cache WHERE timestamp < ?", (cutoff_time,))
            pruned_count = cursor.rowcount

            conn.commit()
            conn.close()

            return pruned_count

        except sqlite3.Error as e:
            print(f"Error pruning cache: {e}")
            return 0
