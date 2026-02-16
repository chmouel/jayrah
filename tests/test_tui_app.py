"""Tests for Textual issue browser app behavior."""

from jayrah.ui.tui.app import IssueBrowserApp


class DummyApp:
    """Minimal app stub for testing event handlers."""

    def __init__(self, auto_choose: bool):
        self.auto_choose = auto_choose
        self.confirm_calls = 0

    def action_confirm_selection(self) -> None:
        self.confirm_calls += 1


def test_row_selected_confirms_in_auto_choose_mode():
    """Pressing Enter on a row confirms selection when auto choose is enabled."""
    app = DummyApp(auto_choose=True)

    IssueBrowserApp._handle_row_selected(app, object())  # type: ignore[arg-type]

    assert app.confirm_calls == 1


def test_row_selected_does_not_confirm_outside_auto_choose_mode():
    """Pressing Enter on a row should not auto-confirm outside choose mode."""
    app = DummyApp(auto_choose=False)

    IssueBrowserApp._handle_row_selected(app, object())  # type: ignore[arg-type]

    assert app.confirm_calls == 0
