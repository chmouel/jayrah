"""Enhanced Input and TextArea widgets with emacs/readline keybindings."""

import re
from textual.binding import Binding
from textual.widgets import Input, TextArea


class EmacsInput(Input):
    """Input widget with emacs/readline keybindings support."""

    BINDINGS = [
        # Basic movement
        Binding("ctrl+a", "cursor_line_start", "Start of line", show=False),
        Binding("ctrl+e", "cursor_line_end", "End of line", show=False),
        Binding("ctrl+f", "cursor_char_right", "Forward char", show=False),
        Binding("ctrl+b", "cursor_char_left", "Backward char", show=False),
        # Deletion
        Binding("ctrl+k", "delete_to_end_of_line", "Delete to end", show=False),
        Binding("ctrl+u", "delete_to_start_of_line", "Delete to start", show=False),
        Binding("ctrl+w", "delete_word_left", "Delete word left", show=False),
        Binding("ctrl+d", "delete_right", "Delete right", show=False),
        Binding("ctrl+h", "delete_left", "Delete left", show=False),
        # Word movement
        Binding("alt+f", "cursor_word_right", "Word right", show=False),
        Binding("alt+b", "cursor_word_left", "Word left", show=False),
        Binding("ctrl+right", "cursor_word_right", "Word right", show=False),
        Binding("ctrl+left", "cursor_word_left", "Word left", show=False),
        # Character operations
        Binding("ctrl+t", "transpose_characters", "Transpose chars", show=False),
    ]

    def action_cursor_line_start(self) -> None:
        """Move cursor to start of line (Ctrl+A)."""
        self.cursor_position = 0

    def action_cursor_line_end(self) -> None:
        """Move cursor to end of line (Ctrl+E)."""
        self.cursor_position = len(self.value)

    def action_cursor_char_right(self) -> None:
        """Move cursor one character to the right (Ctrl+F)."""
        self.cursor_position += 1

    def action_cursor_char_left(self) -> None:
        """Move cursor one character to the left (Ctrl+B)."""
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def action_delete_to_end_of_line(self) -> None:
        """Delete from cursor to end of line (Ctrl+K)."""
        cursor_pos = self.cursor_position
        self.value = self.value[:cursor_pos]
        self.cursor_position = cursor_pos

    def action_delete_to_start_of_line(self) -> None:
        """Delete from start of line to cursor (Ctrl+U)."""
        cursor_pos = self.cursor_position
        self.value = self.value[cursor_pos:]
        self.cursor_position = 0

    def action_delete_word_left(self) -> None:
        """Delete word to the left of cursor (Ctrl+W)."""
        cursor_pos = self.cursor_position
        if cursor_pos == 0:
            return

        # Find start of current word
        text_before = self.value[:cursor_pos]
        # Remove trailing whitespace
        text_before = text_before.rstrip()

        if not text_before:
            # Delete everything before cursor if only whitespace
            self.value = self.value[cursor_pos:]
            self.cursor_position = 0
            return

        # Find word boundary
        word_match = re.search(r"\S+\s*$", text_before)
        if word_match:
            word_start = word_match.start()
            self.value = self.value[:word_start] + self.value[cursor_pos:]
            self.cursor_position = word_start
        else:
            # Fallback: delete everything before cursor
            self.value = self.value[cursor_pos:]
            self.cursor_position = 0

    def action_cursor_word_right(self) -> None:
        """Move cursor to start of next word (Alt+F or Ctrl+Right)."""
        cursor_pos = self.cursor_position
        text_after = self.value[cursor_pos:]

        # Find next word boundary
        match = re.search(r"\s*\S+", text_after)
        if match:
            self.cursor_position = cursor_pos + match.end()
        else:
            # Move to end if no word found
            self.cursor_position = len(self.value)

    def action_cursor_word_left(self) -> None:
        """Move cursor to start of previous word (Alt+B or Ctrl+Left)."""
        cursor_pos = self.cursor_position
        if cursor_pos == 0:
            return

        text_before = self.value[:cursor_pos]

        # Remove trailing whitespace and find previous word
        text_before = text_before.rstrip()
        if not text_before:
            self.cursor_position = 0
            return

        # Find start of current/previous word
        word_match = re.search(r"\S+\s*$", text_before)
        if word_match:
            self.cursor_position = word_match.start()
        else:
            self.cursor_position = 0

    def action_transpose_characters(self) -> None:
        """Transpose characters at cursor (Ctrl+T)."""
        cursor_pos = self.cursor_position
        value = self.value

        if len(value) < 2:
            return

        if cursor_pos == 0:
            # At start of line, swap first two characters
            if len(value) >= 2:
                new_value = value[1] + value[0] + value[2:]
                self.value = new_value
                self.cursor_position = 2
        elif cursor_pos >= len(value):
            # At end of line, swap last two characters
            if len(value) >= 2:
                new_value = value[:-2] + value[-1] + value[-2]
                self.value = new_value
                self.cursor_position = len(new_value)
        else:
            # In middle, swap character before cursor with character at cursor
            new_value = (
                value[: cursor_pos - 1]
                + value[cursor_pos]
                + value[cursor_pos - 1]
                + value[cursor_pos + 1 :]
            )
            self.value = new_value
            self.cursor_position = cursor_pos + 1


class EmacsTextArea(TextArea):
    """TextArea widget with emacs/readline keybindings support."""

    def __init__(self, *args, **kwargs):
        # Disable syntax highlighting and language detection for plain text
        kwargs.setdefault("language", None)
        super().__init__(*args, **kwargs)

    BINDINGS = [
        # Basic movement
        Binding("ctrl+a", "cursor_line_start", "Start of line", show=False),
        Binding("ctrl+e", "cursor_line_end", "End of line", show=False),
        Binding("ctrl+f", "cursor_char_right", "Forward char", show=False),
        Binding("ctrl+b", "cursor_char_left", "Backward char", show=False),
        Binding("ctrl+p", "cursor_line_up", "Previous line", show=False),
        Binding("ctrl+n", "cursor_line_down", "Next line", show=False),
        # Deletion
        Binding("ctrl+k", "delete_to_end_of_line", "Delete to end", show=False),
        Binding("ctrl+u", "delete_to_start_of_line", "Delete to start", show=False),
        Binding("ctrl+w", "delete_word_left", "Delete word left", show=False),
        Binding("ctrl+d", "delete_right", "Delete right", show=False),
        Binding("ctrl+h", "delete_left", "Delete left", show=False),
        # Word movement
        Binding("alt+f", "cursor_word_right", "Word right", show=False),
        Binding("alt+b", "cursor_word_left", "Word left", show=False),
        Binding("ctrl+right", "cursor_word_right", "Word right", show=False),
        Binding("ctrl+left", "cursor_word_left", "Word left", show=False),
        # Character operations
        Binding("ctrl+t", "transpose_characters", "Transpose chars", show=False),
    ]

    def action_cursor_line_start(self) -> None:
        """Move cursor to start of current line (Ctrl+A)."""
        cursor_row, cursor_col = self.cursor_location
        self.cursor_location = (cursor_row, 0)

    def action_cursor_line_end(self) -> None:
        """Move cursor to end of current line (Ctrl+E)."""
        cursor_row, cursor_col = self.cursor_location
        lines = self.text.split("\n")
        if cursor_row < len(lines):
            line_length = len(lines[cursor_row])
            self.cursor_location = (cursor_row, line_length)

    def action_cursor_char_right(self) -> None:
        """Move cursor one character to the right (Ctrl+F)."""
        self.action_cursor_right()  # Use built-in action

    def action_cursor_char_left(self) -> None:
        """Move cursor one character to the left (Ctrl+B)."""
        self.action_cursor_left()  # Use built-in action

    def action_cursor_line_up(self) -> None:
        """Move cursor up one line (Ctrl+P)."""
        self.action_cursor_up()  # Use built-in action

    def action_cursor_line_down(self) -> None:
        """Move cursor down one line (Ctrl+N)."""
        self.action_cursor_down()  # Use built-in action

    def action_delete_to_end_of_line(self) -> None:
        """Delete from cursor to end of current line (Ctrl+K)."""
        cursor_row, cursor_col = self.cursor_location
        lines = self.text.split("\n")

        if cursor_row < len(lines):
            current_line = lines[cursor_row]
            # Delete from cursor to end of line
            lines[cursor_row] = current_line[:cursor_col]
            self.text = "\n".join(lines)

    def action_delete_to_start_of_line(self) -> None:
        """Delete from start of current line to cursor (Ctrl+U)."""
        cursor_row, cursor_col = self.cursor_location
        lines = self.text.split("\n")

        if cursor_row < len(lines):
            current_line = lines[cursor_row]
            # Delete from start of line to cursor
            lines[cursor_row] = current_line[cursor_col:]
            self.text = "\n".join(lines)
            self.cursor_location = (cursor_row, 0)

    def action_delete_word_left(self) -> None:
        """Delete word to the left of cursor (Ctrl+W)."""
        cursor_row, cursor_col = self.cursor_location
        lines = self.text.split("\n")

        if cursor_row >= len(lines) or cursor_col == 0:
            return

        current_line = lines[cursor_row]
        text_before = current_line[:cursor_col]

        # Remove trailing whitespace
        text_before = text_before.rstrip()

        if not text_before:
            # Delete everything before cursor on this line
            lines[cursor_row] = current_line[cursor_col:]
            self.text = "\n".join(lines)
            self.cursor_location = (cursor_row, 0)
            return

        # Find word boundary
        word_match = re.search(r"\S+\s*$", text_before)
        if word_match:
            word_start = word_match.start()
            lines[cursor_row] = current_line[:word_start] + current_line[cursor_col:]
            self.text = "\n".join(lines)
            self.cursor_location = (cursor_row, word_start)
        else:
            # Fallback: delete everything before cursor on this line
            lines[cursor_row] = current_line[cursor_col:]
            self.text = "\n".join(lines)
            self.cursor_location = (cursor_row, 0)

    def action_cursor_word_right(self) -> None:
        """Move cursor to start of next word (Alt+F or Ctrl+Right)."""
        cursor_row, cursor_col = self.cursor_location
        lines = self.text.split("\n")

        if cursor_row >= len(lines):
            return

        current_line = lines[cursor_row]
        text_after = current_line[cursor_col:]

        # Find next word boundary on current line
        match = re.search(r"\s*\S+", text_after)
        if match:
            new_col = cursor_col + match.end()
            self.cursor_location = (cursor_row, new_col)
        else:
            # Move to end of current line if no word found
            self.cursor_location = (cursor_row, len(current_line))

    def action_cursor_word_left(self) -> None:
        """Move cursor to start of previous word (Alt+B or Ctrl+Left)."""
        cursor_row, cursor_col = self.cursor_location
        lines = self.text.split("\n")

        if cursor_row >= len(lines) or cursor_col == 0:
            return

        current_line = lines[cursor_row]
        text_before = current_line[:cursor_col]

        # Remove trailing whitespace and find previous word
        text_before = text_before.rstrip()
        if not text_before:
            self.cursor_location = (cursor_row, 0)
            return

        # Find start of current/previous word
        word_match = re.search(r"\S+\s*$", text_before)
        if word_match:
            self.cursor_location = (cursor_row, word_match.start())
        else:
            self.cursor_location = (cursor_row, 0)

    def action_transpose_characters(self) -> None:
        """Transpose characters at cursor (Ctrl+T)."""
        cursor_row, cursor_col = self.cursor_location
        lines = self.text.split("\n")

        if cursor_row >= len(lines):
            return

        current_line = lines[cursor_row]

        if len(current_line) < 2:
            return

        if cursor_col == 0:
            # At start of line, swap first two characters
            if len(current_line) >= 2:
                new_line = current_line[1] + current_line[0] + current_line[2:]
                lines[cursor_row] = new_line
                self.text = "\n".join(lines)
                self.cursor_location = (cursor_row, 2)
        elif cursor_col >= len(current_line):
            # At end of line, swap last two characters
            if len(current_line) >= 2:
                new_line = current_line[:-2] + current_line[-1] + current_line[-2]
                lines[cursor_row] = new_line
                self.text = "\n".join(lines)
                self.cursor_location = (cursor_row, len(new_line))
        else:
            # In middle, swap character before cursor with character at cursor
            new_line = (
                current_line[: cursor_col - 1]
                + current_line[cursor_col]
                + current_line[cursor_col - 1]
                + current_line[cursor_col + 1 :]
            )
            lines[cursor_row] = new_line
            self.text = "\n".join(lines)
            self.cursor_location = (cursor_row, cursor_col + 1)
