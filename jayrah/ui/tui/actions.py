"""Action handlers for the issue browser application."""

from __future__ import annotations

from typing import Any, cast

from jayrah import utils

from .views import (
    BoardSelectionScreen,
    FuzzyFilterScreen,
    IssueDetailPanel,
    LabelsEditScreen,
    TransitionSelectionScreen,
)


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
        cast(Any, self).notify("🔄 Reloading issues...")

        # Run the reload in a worker thread
        cast(Any, self).run_worker(
            lambda: self._reload_issues(),
            exclusive=True,
            thread=True,
        )

    def action_add_labels(self) -> None:  # noqa: D401
        """Open modal to edit labels for the selected issue."""
        if not cast(Any, self).selected_issue:
            cast(Any, self).notify("No issue selected", severity="warning")
            return

        # Get the current issue data to retrieve existing labels
        try:
            issue_data = cast(Any, self).jayrah_obj.jira.get_issue(
                cast(Any, self).selected_issue
            )
            current_labels = issue_data.get("fields", {}).get("labels", [])

            # Show the labels edit screen
            cast(Any, self).push_screen(
                LabelsEditScreen(
                    self,
                    cast(Any, self).selected_issue,
                    current_labels,
                    cast(Any, self).config,
                )
            )
        except Exception as exc:
            cast(Any, self).notify(f"Error loading issue data: {exc}", severity="error")

    def action_transition_issue(self) -> None:  # noqa: D401
        """Open modal to transition the selected issue to a new status."""
        if not cast(Any, self).selected_issue:
            cast(Any, self).notify("No issue selected", severity="warning")
            return

        # Show the transition selection screen
        try:
            cast(Any, self).push_screen(
                TransitionSelectionScreen(
                    self,
                    cast(Any, self).selected_issue,
                    cast(Any, self).config,
                )
            )
        except Exception as exc:
            cast(Any, self).notify(f"Error loading transitions: {exc}", severity="error")

    def action_help(self) -> None:  # noqa: D401
        """Show help information."""
        cast(Any, self).notify("Showing help…")

    def action_filter(self) -> None:  # noqa: D401
        """Open a simple filter dialog to search across all visible fields."""
        # Show the filter screen
        cast(Any, self).push_screen(FuzzyFilterScreen(self))

    def action_change_board(self) -> None:  # noqa: D401
        """Open modal to select a different board."""
        # Show the board selection screen
        cast(Any, self).push_screen(BoardSelectionScreen(self, cast(Any, self).config))

    def action_cursor_down(self) -> None:  # noqa: D401
        """Move cursor down in the issues table."""
        table = cast(Any, self).query_one("#issues-table")
        table.action_cursor_down()

    def action_cursor_up(self) -> None:  # noqa: D401
        """Move cursor up in the issues table."""
        table = cast(Any, self).query_one("#issues-table")
        table.action_cursor_up()

    def action_scroll_down(self) -> None:  # noqa: D401
        """Scroll down the issue detail panel content."""
        detail_panel = cast(Any, self).query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_down()

    def action_scroll_up(self) -> None:  # noqa: D401
        """Scroll up the issue detail panel content."""
        detail_panel = cast(Any, self).query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_up()

    def action_page_scroll_down(self) -> None:  # noqa: D401
        """Scroll down one page in the issue detail panel content."""
        detail_panel = cast(Any, self).query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_page_down()

    def action_page_scroll_up(self) -> None:  # noqa: D401
        """Scroll up one page in the issue detail panel content."""
        detail_panel = cast(Any, self).query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_page_up()

    def action_open_issue(self) -> None:  # noqa: D401
        """Open the selected issue in the browser."""
        if not cast(Any, self).selected_issue:
            cast(Any, self).notify("No issue selected", severity="error")
            return
        try:
            utils.browser_open_ticket(
                cast(Any, self).selected_issue, cast(Any, self).config
            )
            cast(Any, self).notify(
                f"Opening {cast(Any, self).selected_issue} in browser"
            )
        except Exception as exc:
            cast(Any, self).notify(f"Error opening issue: {exc}", severity="error")

    def action_quit(self) -> None:  # noqa: D401
        """Quit the application."""
        cast(Any, self).exit()  # *app.selected_issue* persists after exit

    def change_board(self, board_name: str) -> None:
        """Change to a different board and reload issues."""
        cast(Any, self).notify(f"🔄 Switching to board: {board_name}...")

        # Run the board change in a worker thread
        cast(Any, self).run_worker(
            lambda: self._change_board_worker(board_name),
            exclusive=True,
            thread=True,
        )

    def _change_board_worker(self, board_name: str) -> None:
        """Worker method to change board and reload issues."""
        try:
            # Import here to avoid circular imports
            from jayrah.ui import boards

            # Get the new board's JQL and order_by
            jql, order_by = boards.check(board_name, cast(Any, self).config)
            if not jql or not order_by:
                cast(Any, self).app.call_from_thread(
                    lambda: cast(Any, self).notify(
                        f"Error: Invalid board or missing JQL: {board_name}",
                        severity="error",
                    )
                )
                return

            # Update the command for this app instance
            cast(Any, self).command = board_name
            cast(Any, self).jql = jql
            cast(Any, self).order_by = order_by

            # Clear cache and fetch new issues
            cast(Any, self).jayrah_obj.jira.cache.clear()
            new_issues = cast(Any, self).jayrah_obj.issues_client.list_issues(
                jql, order_by=order_by, use_cache=False
            )

            # Update the UI in the main thread
            cast(Any, self).app.call_from_thread(
                lambda: self._update_issues_after_board_change(new_issues, board_name)
            )
        except Exception as e:
            err = str(e)
            cast(Any, self).app.call_from_thread(
                lambda err=err: cast(Any, self).notify(
                    f"Error changing board: {err}", severity="error"
                )
            )

    def _update_issues_after_board_change(
        self, new_issues: list, board_name: str
    ) -> None:
        """Update the UI after changing boards."""
        if cast(Any, self).verbose:
            cast(Any, self).log(
                f"Board changed to {board_name}. New issues: {len(new_issues)}"
            )

        cast(Any, self).issues = new_issues
        cast(Any, self).apply_fuzzy_filter("", msg=f"Switched to board: {board_name}")

        # Clear the detail panel
        detail_panel = cast(Any, self).query_one(IssueDetailPanel)
        detail_panel.ticket_cache = {}
        detail_panel.update_issue(None, cast(Any, self).config)
        cast(Any, self).selected_issue = None

        cast(Any, self).notify(
            f"✅ Switched to board: {board_name} ({len(new_issues)} issues)"
        )

    def _reload_issues(self) -> None:
        """Worker method to reload issues."""
        try:
            # Clear cache and fetch new issues
            cast(Any, self).jayrah_obj.jira.cache.clear()
            new_issues = cast(Any, self).jayrah_obj.issues_client.list_issues(
                cast(Any, self).jql, order_by=cast(Any, self).order_by, use_cache=False
            )

            # Update the UI in the main thread
            cast(Any, self).app.call_from_thread(
                lambda: self._update_issues_after_reload(new_issues)
            )
        except Exception as e:
            err = str(e)
            cast(Any, self).app.call_from_thread(
                lambda err=err: cast(Any, self).notify(
                    f"Error reloading issues: {err}", severity="error"
                )
            )

    def _update_issues_after_reload(self, new_issues: list) -> None:
        """Update the UI after reloading issues."""
        if cast(Any, self).verbose:
            cast(Any, self).log(f"Reloaded Issues are {new_issues}")

        cast(Any, self).issues = new_issues
        cast(Any, self).apply_fuzzy_filter(
            "", msg="Reloading issues and clearing cache"
        )

        detail_panel = cast(Any, self).query_one(IssueDetailPanel)
        detail_panel.ticket_cache = {}
        detail_panel.update_issue(
            detail_panel.ticket, cast(Any, self).config, use_cache=False
        )

        cast(Any, self).notify("✅ Issues reloaded successfully")
