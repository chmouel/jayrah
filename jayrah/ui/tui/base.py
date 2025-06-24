"""Base classes and mixins for the TUI components."""

from textual.screen import ModalScreen
import importlib


class JayrahAppMixin:
    """Mixin providing common Jayrah functionality for apps."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.verbose = self.config.get("verbose", False)
        # Lazy import boards to avoid circular import
        boards = importlib.import_module("jayrah.ui.boards")
        self.jayrah_obj = boards.Boards(self.config)


class BaseModalScreen(ModalScreen):
    """Base class for modal screens in the issue browser."""

    def __init__(self, parent):
        super().__init__()
        self._parent = parent
        self._popped = False

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.safe_pop_screen()

    def safe_pop_screen(self) -> bool:
        """Safely pop screen, preventing multiple pops. Returns True if popped, False if already popped."""
        if not self._popped and self.is_mounted:
            self._popped = True
            self._parent.pop_screen()
            return True
        return False
