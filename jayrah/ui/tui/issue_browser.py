"""
This file is no longer used - functionality has been moved to the modular structure.
Please use imports from:
- .app import IssueBrowserApp, run_textual_browser
- .views import IssueDetailPanel, LabelsEditScreen, FuzzyFilterScreen
- .actions import IssueBrowserActions
- .base import JayrahAppMixin, BaseModalScreen
- .helpers import get_row_data_for_issue, filter_issues_by_text
"""

import warnings

warnings.warn(
    "jayrah.ui.tui.issue_browser is deprecated. "
    "Use imports from jayrah.ui.tui submodules instead.",
    DeprecationWarning,
    stacklevel=2,
)
