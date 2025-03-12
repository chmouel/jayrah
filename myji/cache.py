import hashlib
import json
import os
import time
from pathlib import Path

from . import utils


class JiraCache:
    """Cache handler for Jira API responses"""

    def __init__(self, cache_dir=None, cache_ttl=3600, verbose=False):
        """
        Initialize the cache handler

        Args:
            cache_dir (str): Directory to store cache files (defaults to ~/.cache/myji/)
            cache_ttl (int): Time to live for cache entries in seconds (default: 1 hour)
            verbose (bool): Enable verbose logging
        """
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.cache/myji")

        self.cache_dir = Path(cache_dir)
        self.cache_ttl = cache_ttl
        self.verbose = verbose

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        if self.verbose:
            cache_files = list(self.cache_dir.glob("*.json"))
            utils.log(f"Cache initialized: directory={self.cache_dir}, TTL={self.cache_ttl}s", 
                     "DEBUG", verbose_only=True, verbose=self.verbose)
            utils.log(f"Found {len(cache_files)} existing cache files", 
                     "DEBUG", verbose_only=True, verbose=self.verbose)

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
        hash_key = hashlib.md5(key_string.encode()).hexdigest()
        
        if self.verbose:
            utils.log(f"Generated cache key: {hash_key} for URL: {url}", 
                     "DEBUG", verbose_only=True, verbose=self.verbose)
            
        return hash_key

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
        
        if self.verbose:
            utils.log(f"Looking for cache at: {cache_path}", 
                     "DEBUG", verbose_only=True, verbose=self.verbose)

        if not cache_path.exists():
            if self.verbose:
                utils.log(f"Cache miss: File not found", 
                         "DEBUG", verbose_only=True, verbose=self.verbose)
            return None

        try:
            with open(cache_path, "r") as f:
                cached_data = json.load(f)
                
            if self.verbose:
                cached_time = time.strftime('%Y-%m-%d %H:%M:%S', 
                                          time.localtime(cached_data['timestamp']))
                utils.log(f"Cache file found, created at: {cached_time}", 
                         "DEBUG", verbose_only=True, verbose=self.verbose)

            # Check if cache has expired
            age = time.time() - cached_data['timestamp']
            if age > self.cache_ttl:
                if self.verbose:
                    utils.log(f"Cache expired: Age is {int(age)}s, TTL is {self.cache_ttl}s", 
                             "DEBUG", verbose_only=True, verbose=self.verbose)
                return None
                
            if self.verbose:
                utils.log(f"Cache hit: Using cached data ({int(age)}s old)", 
                         "SUCCESS", verbose_only=True, verbose=self.verbose)

            return cached_data["data"]
        except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
            if self.verbose:
                utils.log(f"Cache error: {e}", "WARNING", verbose_only=True, verbose=self.verbose)
            # Invalid or corrupt cache
            return None

    def set(self, url, response_data, params=None, json_data=None):
        """Save response data to cache"""
        cache_key = self._get_cache_key(url, params, json_data)
        cache_path = self._get_cache_path(cache_key)
        
        if self.verbose:
            utils.log(f"Saving response to cache: {cache_path}", 
                     "DEBUG", verbose_only=True, verbose=self.verbose)

        cached_data = {"timestamp": time.time(), "data": response_data}
        
        try:
            with open(cache_path, "w") as f:
                json.dump(cached_data, f)
                
            if self.verbose:
                utils.log(f"Successfully wrote {len(str(response_data))} bytes to cache", 
                         "SUCCESS", verbose_only=True, verbose=self.verbose)
        except Exception as e:
            if self.verbose:
                utils.log(f"Error saving to cache: {e}", "ERROR", verbose_only=True, verbose=self.verbose)

    def clear(self):
        """Clear all cached data"""
        if self.verbose:
            utils.log(f"Clearing all cache files from {self.cache_dir}", 
                     "WARNING", verbose_only=True, verbose=self.verbose)
            
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
                if self.verbose:
                    utils.log(f"Deleted: {cache_file}", 
                             "DEBUG", verbose_only=True, verbose=self.verbose)
            except OSError as e:
                if self.verbose:
                    utils.log(f"Failed to delete {cache_file}: {e}", 
                             "ERROR", verbose_only=True, verbose=self.verbose)
        
        if self.verbose:
            utils.log(f"Cleared {count} cache files", "SUCCESS", verbose_only=True, verbose=self.verbose)
