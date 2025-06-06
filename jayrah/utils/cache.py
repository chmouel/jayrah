"""Caching utilities for Jayrah Jira client."""

import hashlib
import json
import pickle
import sqlite3
import time
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from jayrah import utils


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
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._init_db()
        self._preloaded_cache = None  # Will hold preloaded cache if used

    def _init_db(self):
        """Initialize the SQLite database."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    data BLOB,
                    timestamp REAL
                )
            """)
            self._conn.commit()

    def _get_connection(self):
        """Get the persistent connection (for compatibility)."""
        return self._conn

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

    def preload_cache(self):
        """Preload all cache entries into memory as a dict {key: (data, timestamp)}."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT key, data, timestamp FROM cache")
            rows = cursor.fetchall()
            self._preloaded_cache = {k: (d, t) for k, d, t in rows}

    def get(
        self, url: str, params: Optional[Dict] = None, data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Get a cached response."""
        if self.config.get("no_cache"):
            return None
        key = self._generate_key(url, params, data)
        try:
            with self._lock:
                if self._preloaded_cache is not None:
                    result = self._preloaded_cache.get(key)
                else:
                    cursor = self._conn.cursor()
                    cursor.execute(
                        "SELECT data, timestamp FROM cache WHERE key = ?", (key,)
                    )
                    result = cursor.fetchone()
            if not result:
                return None
            cached_data, timestamp = result
            if time.time() - timestamp > self.cache_ttl:
                self._remove_entry(key)
                return None
            return pickle.loads(cached_data)
        except (sqlite3.Error, pickle.PickleError) as e:
            utils.log(f"Error retrieving from cache: {e}")
            return None

    def set(
        self,
        url: str,
        data: Any,
        params: Optional[Dict] = None,
        request_data: Optional[Dict] = None,
    ) -> None:
        if self.config.get("no_cache"):
            return
        key = self._generate_key(url, params, request_data)
        timestamp = time.time()
        try:
            pickled_data = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO cache (key, data, timestamp) VALUES (?, ?, ?)",
                    (key, pickled_data, timestamp),
                )
                self._conn.commit()
                if self._preloaded_cache is not None:
                    self._preloaded_cache[key] = (pickled_data, timestamp)
        except (sqlite3.Error, pickle.PickleError) as e:
            utils.log(f"Error setting cache: {e}")

    def _remove_entry(self, key: str) -> None:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
                self._conn.commit()
                if self._preloaded_cache is not None and key in self._preloaded_cache:
                    del self._preloaded_cache[key]
        except sqlite3.Error as e:
            utils.log(f"Error removing cache entry: {e}")

    def clear(self) -> None:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM cache")
                self._conn.commit()
                if self._preloaded_cache is not None:
                    self._preloaded_cache.clear()
        except sqlite3.Error as e:
            utils.log(f"Error clearing cache: {e}")

    def prune(self, max_age: Optional[int] = None) -> int:
        if max_age is None:
            max_age = self.cache_ttl
        cutoff_time = time.time() - max_age
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM cache WHERE timestamp < ?", (cutoff_time,))
                pruned_count = cursor.rowcount
                self._conn.commit()
                if self._preloaded_cache is not None:
                    # Remove pruned keys from preloaded cache
                    to_remove = [
                        k
                        for k, (_, t) in self._preloaded_cache.items()
                        if t < cutoff_time
                    ]
                    for k in to_remove:
                        del self._preloaded_cache[k]
                return pruned_count
        except sqlite3.Error as e:
            utils.log(f"Error pruning cache: {e}")
            return 0
