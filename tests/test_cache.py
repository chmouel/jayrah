import time

import pytest

from jayrah.cache import JiraCache


def test_init_creates_cache_dir(tmp_path):
    """Test that init creates the cache directory if it doesn't exist."""
    cache_dir = tmp_path / "nonexistent_dir"
    config = {"cache_ttl": 3600, "verbose": True}
    cache = JiraCache(config, cache_dir=cache_dir)
    assert cache_dir.exists()
    assert cache_dir.is_dir()


def test_get_cache_key_generation():
    """Test generation of cache keys from URL and parameters."""
    config = {"cache_ttl": 3600}
    cache = JiraCache(config)

    # Test with just URL
    key1 = cache._get_cache_key("https://jira.example.com/api/issue")
    assert isinstance(key1, str)
    assert len(key1) > 0

    # Test with URL and params
    key2 = cache._get_cache_key(
        "https://jira.example.com/api/issue", {"id": "TEST-123"}
    )
    assert key2 != key1  # Different params should yield different keys

    # Test with URL, params, and JSON data
    key3 = cache._get_cache_key(
        "https://jira.example.com/api/issue",
        {"id": "TEST-123"},
        {"summary": "Test issue"},
    )
    assert key3 != key2  # Different JSON should yield different keys


def test_set_and_get_cache(tmp_path):
    """Test setting and retrieving data from cache."""
    cache_dir = tmp_path / "cache"
    config = {"cache_ttl": 3600}
    cache = JiraCache(config, cache_dir=cache_dir)

    url = "https://jira.example.com/api/issue/TEST-123"
    test_data = {"key": "TEST-123", "summary": "Test issue"}

    # Set data in cache
    cache.set(url, test_data)

    # Get data from cache
    cached_data = cache.get(url)
    assert cached_data == test_data


def test_cache_expiration(tmp_path):
    """Test that expired cache entries are not returned."""
    cache_dir = tmp_path / "cache"
    config = {"cache_ttl": 1}  # 1 second TTL for quick testing
    cache = JiraCache(config, cache_dir=cache_dir)

    url = "https://jira.example.com/api/issue/TEST-123"
    test_data = {"key": "TEST-123", "summary": "Test issue"}

    # Set data in cache
    cache.set(url, test_data)

    # Get data immediately (should be found)
    assert cache.get(url) == test_data

    # Wait for cache to expire
    time.sleep(1.1)

    # Get data after expiration (should return None)
    assert cache.get(url) is None


def test_cache_clear(tmp_path):
    """Test clearing all cache files."""
    cache_dir = tmp_path / "cache"
    config = {"cache_ttl": 3600, "verbose": True}
    cache = JiraCache(config, cache_dir=cache_dir)

    # Create some cache entries
    urls = [
        "https://jira.example.com/api/issue/TEST-123",
        "https://jira.example.com/api/issue/TEST-124",
        "https://jira.example.com/api/issue/TEST-125",
    ]

    for i, url in enumerate(urls):
        cache.set(url, {"key": f"TEST-{123 + i}", "summary": f"Test issue {i + 1}"})

    # Check all cache files exist
    assert len(list(cache_dir.glob("*.json"))) == 3

    # Clear cache
    cache.clear()

    # Check all cache files are gone
    assert len(list(cache_dir.glob("*.json"))) == 0


def test_invalid_cache_data(tmp_path):
    """Test handling of invalid cache data."""
    cache_dir = tmp_path / "cache"
    config = {"cache_ttl": 3600}
    cache = JiraCache(config, cache_dir=cache_dir)

    url = "https://jira.example.com/api/issue/TEST-123"

    # Create an invalid cache file
    cache_key = cache._get_cache_key(url)
    cache_path = cache._get_cache_path(cache_key)

    with open(cache_path, "w") as f:
        f.write("This is not valid JSON")

    # Try to get the data (should return None due to invalid JSON)
    assert cache.get(url) is None
