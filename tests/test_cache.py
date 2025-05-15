import tempfile
import time
from pathlib import Path
from unittest import TestCase, mock

from jayrah.cache import JiraCache


class TestJiraCache(TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name)

        # Mock config
        self.config = {
            "cache_dir": self.cache_dir,
            "cache_ttl": 300,  # 5 minutes
        }

        self.cache = JiraCache(self.config)

    def tearDown(self):
        # Close the temporary directory
        self.temp_dir.cleanup()

    def test_init(self):
        """Test cache initialization."""
        # Check if the cache directory was created
        self.assertTrue(self.cache_dir.exists())

        # Check if the database file was created
        db_path = self.cache_dir / "cache.db"
        self.assertTrue(db_path.exists())

    def test_cache_set_get(self):
        """Test setting and getting cache entries."""
        url = "http://example.com/api/v1/test"
        data = {"key1": "value1", "key2": [1, 2, 3, 4]}
        params = {"param1": "value1", "param2": "value2"}

        # Set the cache entry
        self.cache.set(url, data, params)

        # Get the cache entry
        cached_data = self.cache.get(url, params)

        # Check if the cached data matches the original data
        self.assertEqual(cached_data, data)

    def test_cache_expiration(self):
        """Test cache expiration."""
        url = "http://example.com/api/v1/test"
        data = {"key": "value"}

        # Set the cache entry
        self.cache.set(url, data)

        # Get the cache entry (should be cached)
        cached_data1 = self.cache.get(url)
        self.assertEqual(cached_data1, data)

        # Mock time.time() to simulate cache expiration
        with mock.patch(
            "time.time", return_value=time.time() + 600
        ):  # 10 minutes later
            # Get the cache entry (should be expired)
            cached_data2 = self.cache.get(url)
            self.assertIsNone(cached_data2)

    def test_cache_with_different_params(self):
        """Test cache with different parameters."""
        url = "http://example.com/api/v1/test"
        data = {"key": "value"}

        params1 = {"param": "value1"}
        params2 = {"param": "value2"}

        # Set cache entry with params1
        self.cache.set(url, data, params1)

        # Get cache entry with params1 (should be cached)
        cached_data1 = self.cache.get(url, params1)
        self.assertEqual(cached_data1, data)

        # Get cache entry with params2 (should not be cached)
        cached_data2 = self.cache.get(url, params2)
        self.assertIsNone(cached_data2)

    def test_cache_clear(self):
        """Test clearing the cache."""
        url1 = "http://example.com/api/v1/test1"
        url2 = "http://example.com/api/v1/test2"
        data = {"key": "value"}

        # Set cache entries
        self.cache.set(url1, data)
        self.cache.set(url2, data)

        # Clear the cache
        self.cache.clear()

        # Get cache entries (should be None)
        cached_data1 = self.cache.get(url1)
        cached_data2 = self.cache.get(url2)

        self.assertIsNone(cached_data1)
        self.assertIsNone(cached_data2)

    def test_cache_prune(self):
        """Test pruning the cache."""
        url1 = "http://example.com/api/v1/test1"
        url2 = "http://example.com/api/v1/test2"
        data = {"key": "value"}

        # Set cache entries
        with mock.patch("time.time", return_value=time.time() - 600):  # 10 minutes ago
            self.cache.set(url1, data)

        self.cache.set(url2, data)

        # Prune the cache with max_age of 5 minutes
        pruned_count = self.cache.prune(300)

        # url1 should be pruned, url2 should still be cached
        self.assertEqual(pruned_count, 1)

        cached_data1 = self.cache.get(url1)
        cached_data2 = self.cache.get(url2)

        self.assertIsNone(cached_data1)
        self.assertEqual(cached_data2, data)

    def test_complex_data_structures(self):
        """Test caching complex data structures."""
        url = "http://example.com/api/v1/test"
        data = {
            "string": "test",
            "number": 123,
            "list": [1, 2, 3, {"key": "value"}],
            "dict": {"key1": "value1", "key2": [4, 5, 6]},
            "nested": {"level1": {"level2": {"level3": ["nested", "list"]}}},
        }

        # Set the cache entry
        self.cache.set(url, data)

        # Get the cache entry
        cached_data = self.cache.get(url)

        # Check if the cached data matches the original data
        self.assertEqual(cached_data, data)

    def test_no_cache_config(self):
        """Test with no_cache config option."""
        config = {"cache_dir": self.cache_dir, "no_cache": True}

        cache = JiraCache(config)

        url = "http://example.com/api/v1/test"
        data = {"key": "value"}

        # Set cache entry
        cache.set(url, data)

        # Get cache entry (should be None because caching is disabled)
        cached_data = cache.get(url)

        self.assertIsNone(cached_data)
