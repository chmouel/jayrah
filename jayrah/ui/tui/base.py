"""Base classes and mixins for the TUI components."""

from textual.screen import ModalScreen
from .. import boards


class JayrahAppMixin:
    """Mixin providing common Jayrah functionality for apps."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.verbose = self.config.get("verbose", False)
        self.jayrah_obj = boards.Boards(self.config)


class BaseModalScreen(ModalScreen):
    """Base class for modal screens in the issue browser."""

    def __init__(self, parent):
        super().__init__()
        self._parent = parent

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self._parent.pop_screen()
