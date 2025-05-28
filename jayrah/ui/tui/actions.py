"""Action handlers for the issue browser application."""

from jayrah import utils
from .views import FuzzyFilterScreen, LabelsEditScreen, IssueDetailPanel


class IssueBrowserActions:
    """
    Mixin class containing all action handlers for the issue browser.

    This class should be mixed with a Textual App that has the following attributes:
    - notify, run_worker, push_screen, query_one, exit, log, app (from Textual App)
    - selected_issue, jayrah_obj, config, verbose, jql, order_by, issues (app-specific)
    - apply_fuzzy_filter method
    """

    def action_reload(self) -> None:  # noqa: D401
        """Reload issues asynchronously with loading state."""
        # Show loading state
        self.notify("🔄 Reloading issues...")

        # Run the reload in a worker thread
        self.run_worker(
            self._reload_issues,
            exclusive=True,
            thread=True,
        )

    def action_add_labels(self) -> None:  # noqa: D401
        """Open modal to edit labels for the selected issue."""
        if not self.selected_issue:
            self.notify("No issue selected", severity="warning")
            return

        # Get the current issue data to retrieve existing labels
        try:
            issue_data = self.jayrah_obj.jira.get_issue(self.selected_issue)
            current_labels = issue_data.get("fields", {}).get("labels", [])

            # Show the labels edit screen
            self.push_screen(
                LabelsEditScreen(self, self.selected_issue, current_labels)
            )
        except Exception as exc:
            self.notify(f"Error loading issue data: {exc}", severity="error")

    def action_help(self) -> None:  # noqa: D401
        """Show help information."""
        self.notify("Showing help…")

    def action_filter(self) -> None:  # noqa: D401
        """Open a simple filter dialog to search across all visible fields."""
        # Show the filter screen
        self.push_screen(FuzzyFilterScreen(self))

    def action_cursor_down(self) -> None:  # noqa: D401
        """Move cursor down in the issues table."""
        table = self.query_one("#issues-table")
        table.action_cursor_down()

    def action_cursor_up(self) -> None:  # noqa: D401
        """Move cursor up in the issues table."""
        table = self.query_one("#issues-table")
        table.action_cursor_up()

    def action_scroll_down(self) -> None:  # noqa: D401
        """Scroll down the issue detail panel content."""
        detail_panel = self.query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_down()

    def action_scroll_up(self) -> None:  # noqa: D401
        """Scroll up the issue detail panel content."""
        detail_panel = self.query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_up()

    def action_page_scroll_down(self) -> None:  # noqa: D401
        """Scroll down one page in the issue detail panel content."""
        detail_panel = self.query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_page_down()

    def action_page_scroll_up(self) -> None:  # noqa: D401
        """Scroll up one page in the issue detail panel content."""
        detail_panel = self.query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_page_up()

    def action_open_issue(self) -> None:  # noqa: D401
        """Open the selected issue in the browser."""
        if not self.selected_issue:
            self.notify("No issue selected", severity="error")
            return
        try:
            utils.browser_open_ticket(self.selected_issue, self.config)
            self.notify(f"Opening {self.selected_issue} in browser")
        except Exception as exc:
            self.notify(f"Error opening issue: {exc}", severity="error")

    def action_quit(self) -> None:  # noqa: D401
        """Quit the application."""
        self.exit()  # *app.selected_issue* persists after exit

    def _reload_issues(self) -> None:
        """Worker method to reload issues."""
        try:
            # Clear cache and fetch new issues
            self.jayrah_obj.jira.cache.clear()
            new_issues = self.jayrah_obj.issues_client.list_issues(
                self.jql, order_by=self.order_by, use_cache=False
            )

            # Update the UI in the main thread
            self.app.call_from_thread(
                lambda: self._update_issues_after_reload(new_issues)
            )
        except Exception as e:
            err = str(e)
            self.app.call_from_thread(
                lambda err=err: self.notify(
                    f"Error reloading issues: {err}", severity="error"
                )
            )

    def _update_issues_after_reload(self, new_issues: list) -> None:
        """Update the UI after reloading issues."""
        if self.verbose:
            self.log(f"Reloaded Issues are {new_issues}")

        self.issues = new_issues
        self.apply_fuzzy_filter("", msg="Reloading issues and clearing cache")

        detail_panel = self.query_one(IssueDetailPanel)
        detail_panel.ticket_cache = {}
        detail_panel.update_issue(detail_panel.ticket, self.config, use_cache=False)

        self.notify("✅ Issues reloaded successfully")
