"""Tests for the search functionality in the boards module."""

from jayrah.ui import boards


def test_build_search_jql():
    """Test the build_search_jql function."""
    base_jql = "project = TEST"

    # Test with no search terms
    result = boards.build_search_jql(base_jql, [], False, False)
    assert result == base_jql

    # Test with one search term and AND logic
    search_terms = ["test"]
    result = boards.build_search_jql(base_jql, search_terms, False, False)
    expected = f'({base_jql}) AND ((summary ~ "test" OR description ~ "test"))'
    assert result == expected

    # Test with multiple search terms and AND logic
    search_terms = ["test1", "test2"]
    result = boards.build_search_jql(base_jql, search_terms, False, False)
    expected = f'({base_jql}) AND ((summary ~ "test1" OR description ~ "test1") AND (summary ~ "test2" OR description ~ "test2"))'
    assert result == expected

    # Test with multiple search terms and OR logic
    search_terms = ["test1", "test2"]
    result = boards.build_search_jql(base_jql, search_terms, True, False)
    expected = f'({base_jql}) AND ((summary ~ "test1" OR description ~ "test1") OR (summary ~ "test2" OR description ~ "test2"))'
    assert result == expected


def test_build_search_jql_with_filters():
    """Test the build_search_jql function with field filters."""
    base_jql = "project = TEST"

    # Test with a single filter
    filters = ["status=Open"]
    result = boards.build_search_jql(base_jql, [], False, False, filters)
    expected = f"({base_jql}) AND (status = Open)"
    assert result == expected

    # Test with multiple filters
    filters = ["status=Open", "priority=High"]
    result = boards.build_search_jql(base_jql, [], False, False, filters)
    expected = f"({base_jql}) AND (status = Open AND priority = High)"
    assert result == expected

    # Test with a filter that contains spaces in value
    filters = ["status=Code Review"]
    result = boards.build_search_jql(base_jql, [], False, False, filters)
    expected = f'({base_jql}) AND (status = "Code Review")'
    assert result == expected

    # Test with both search terms and filters
    search_terms = ["test"]
    filters = ["status=Open"]
    result = boards.build_search_jql(base_jql, search_terms, False, False, filters)
    expected = f'(({base_jql}) AND ((summary ~ "test" OR description ~ "test"))) AND (status = Open)'
    assert result == expected

    # Test with already quoted value
    filters = ['status="In Progress"']
    result = boards.build_search_jql(base_jql, [], False, False, filters)
    expected = f'({base_jql}) AND (status = "In Progress")'
    assert result == expected

    # Test with invalid filter format (should be ignored in the JQL)
    filters = ["invalid_filter"]
    result = boards.build_search_jql(base_jql, [], False, False, filters)
    expected = base_jql
    assert result == expected


def test_format_search_terms():
    """Test the format_search_terms function."""
    # Test with no search terms
    result = boards.format_search_terms([])
    assert result == ""

    # Test with one search term
    search_terms = ["test"]
    result = boards.format_search_terms(search_terms)
    expected = "'test'"
    assert result == expected

    # Test with multiple search terms and AND logic
    search_terms = ["test1", "test2"]
    result = boards.format_search_terms(search_terms, False)
    expected = "'test1' AND 'test2'"
    assert result == expected

    # Test with multiple search terms and OR logic
    search_terms = ["test1", "test2"]
    result = boards.format_search_terms(search_terms, True)
    expected = "'test1' OR 'test2'"
    assert result == expected


def test_show_no_issues_message(capsys):
    """Test the show_no_issues_message function with filters."""
    # Test with no search terms or filters
    boards.show_no_issues_message()
    captured = capsys.readouterr()
    assert "No issues found" in captured.err

    # Test with search terms only
    boards.show_no_issues_message(["term1", "term2"], False)
    captured = capsys.readouterr()
    assert "No issues found matching with 'term1' AND 'term2'" in captured.err

    # Test with filters only
    boards.show_no_issues_message(filters=["status=Open"])
    captured = capsys.readouterr()
    assert "No issues found matching with filters: status=Open" in captured.err

    # Test with both search terms and filters
    boards.show_no_issues_message(["test"], False, ["status=Open"])
    captured = capsys.readouterr()
    assert "No issues found matching with 'test', filters: status=Open" in captured.err
