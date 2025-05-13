"""
Test script for the search refactoring.
"""

import sys
from pathlib import Path

# Add parent directory to import path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jayrah import boards


def test_build_search_jql():
    """Test the build_search_jql function"""
    base_jql = "project = TEST"

    # Test with no search terms
    result = boards.build_search_jql(base_jql, [], False, False)
    assert result == base_jql, f"Expected {base_jql}, got {result}"

    # Test with one search term and AND logic
    search_terms = ["test"]
    result = boards.build_search_jql(base_jql, search_terms, False, False)
    expected = f'({base_jql}) AND ((summary ~ "test" OR description ~ "test"))'
    assert result == expected, f"Expected {expected}, got {result}"

    # Test with multiple search terms and AND logic
    search_terms = ["test1", "test2"]
    result = boards.build_search_jql(base_jql, search_terms, False, False)
    expected = f'({base_jql}) AND ((summary ~ "test1" OR description ~ "test1") AND (summary ~ "test2" OR description ~ "test2"))'
    assert result == expected, f"Expected {expected}, got {result}"

    # Test with multiple search terms and OR logic
    search_terms = ["test1", "test2"]
    result = boards.build_search_jql(base_jql, search_terms, True, False)
    expected = f'({base_jql}) AND ((summary ~ "test1" OR description ~ "test1") OR (summary ~ "test2" OR description ~ "test2"))'
    assert result == expected, f"Expected {expected}, got {result}"

    print("All build_search_jql tests passed!")


def test_format_search_terms():
    """Test the format_search_terms function"""
    # Test with no search terms
    result = boards.format_search_terms([])
    assert result == "", f"Expected empty string, got {result}"

    # Test with one search term
    search_terms = ["test"]
    result = boards.format_search_terms(search_terms)
    expected = "'test'"
    assert result == expected, f"Expected {expected}, got {result}"

    # Test with multiple search terms and AND logic
    search_terms = ["test1", "test2"]
    result = boards.format_search_terms(search_terms, False)
    expected = "'test1' AND 'test2'"
    assert result == expected, f"Expected {expected}, got {result}"

    # Test with multiple search terms and OR logic
    search_terms = ["test1", "test2"]
    result = boards.format_search_terms(search_terms, True)
    expected = "'test1' OR 'test2'"
    assert result == expected, f"Expected {expected}, got {result}"

    print("All format_search_terms tests passed!")


if __name__ == "__main__":
    try:
        test_build_search_jql()
        test_format_search_terms()
        print("\nAll tests passed successfully!")
    except AssertionError as e:
        print(f"\nTest failed: {e}", file=sys.stderr)
        sys.exit(1)
