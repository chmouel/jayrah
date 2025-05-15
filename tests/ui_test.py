#!/usr/bin/env python3
"""Test script for the Textual UI"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from jayrah.ui.issue_browser import IssueBrowserApp


def main():
    """Run a test of the Textual UI with sample data"""
    # Create some sample issues
    sample_issues = []
    for i in range(1, 10):
        sample_issues.append({
            "key": f"TEST-{i}",
            "fields": {
                "summary": f"Test issue {i}",
                "issuetype": {"name": "Bug" if i % 3 == 0 else "Story"},
                "assignee": {"displayName": "John Doe", "emailAddress": "john.doe@example.com"},
                "reporter": {"displayName": "Jane Smith", "emailAddress": "jane.smith@example.com"},
                "created": "2023-05-12T10:30:00.000+0000",
                "updated": "2023-05-13T15:45:00.000+0000",
                "status": {"name": "In Progress" if i % 2 == 0 else "To Do"}
            }
        })
    
    # Sample config
    config = {
        "jayrah_path": os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'jayrah')),
        "jira_server": "https://example.atlassian.net"
    }
    
    # Run the UI
    app = IssueBrowserApp(sample_issues, config, "browse")
    app.run()
    
    # Print the selected issue (if any)
    print(f"Selected issue: {app.selected_issue}")


if __name__ == "__main__":
    main()
