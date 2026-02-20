"""
Converts Markdown to JIRA markup language.
Handles headings, formatting, lists, links, code, blockquotes, tables, images, etc.
"""

import re
from typing import Any

CODE_BLOCK_LANGS_TO_JIRA = {
    "sh": "bash",
}


def convert(markdown_text):
    """
    Converts Markdown to JIRA markup language.
    Handles headings, formatting, lists, links, code, blockquotes, tables, images, etc.
    """
    lines = markdown_text.split("\n")
    converted_lines = []
    in_code_block = False
    in_fenced_code = False
    in_quote_block = False
    code_block_lang = ""
    quote_lines = []

    for i, line in enumerate(lines):
        # --- Fenced Code Blocks (check first) ---
        if re.match(r"^```(\w*)$", line):
            if not in_code_block:
                in_code_block = True
                in_fenced_code = True
                code_block_lang = re.match(r"^```(\w*)$", line).group(1)
                if CODE_BLOCK_LANGS_TO_JIRA.get(code_block_lang):
                    code_block_lang = CODE_BLOCK_LANGS_TO_JIRA[code_block_lang]
                if code_block_lang:
                    converted_lines.append(f"{{code:{code_block_lang}}}")
                else:
                    converted_lines.append("{code}")
                continue
            in_code_block = False
            in_fenced_code = False
            converted_lines.append("{code}")
            continue

        if in_code_block:
            converted_lines.append(line)
            continue

        # --- Indented Code Blocks (only if not in fenced) ---
        if (re.match(r"^    ", line) or re.match(r"^\t", line)) and not in_fenced_code:
            if not in_code_block:
                converted_lines.append("{code}")
                in_code_block = True
            code_line = re.sub(r"^    ", "", line)
            code_line = re.sub(r"^\t", "", code_line)
            converted_lines.append(code_line)
            continue
        if in_code_block and not in_fenced_code:
            converted_lines.append("{code}")
            in_code_block = False

        # --- Multi-line Blockquotes ---
        if re.match(r"^\s*>\s?", line):
            if not in_quote_block:
                in_quote_block = True
                quote_lines = []
            quote_content = re.sub(r"^\s*>\s?", "", line)
            quote_lines.append(quote_content)
            continue
        if in_quote_block:
            converted_lines.append("{quote}")
            converted_lines.extend(quote_lines)
            converted_lines.append("{quote}")
            in_quote_block = False
            quote_lines = []

        # --- Tables ---
        if "|" in line and line.strip().startswith("|") and line.strip().endswith("|"):
            if re.match(r"^\s*\|[\s\-:]+\|\s*$", line):
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if i + 1 < len(lines) and re.match(r"^\s*\|[\s\-:]+\|\s*$", lines[i + 1]):
                converted_lines.append("||" + "||".join(cells) + "||")
            else:
                converted_lines.append("|" + "|".join(cells) + "|")
            continue

        # --- Headings ---
        line = re.sub(r"^\s*######\s+(.*)", r"h6. \1", line)
        line = re.sub(r"^\s*#####\s+(.*)", r"h5. \1", line)
        line = re.sub(r"^\s*####\s+(.*)", r"h4. \1", line)
        line = re.sub(r"^\s*###\s+(.*)", r"h3. \1", line)
        line = re.sub(r"^\s*##\s+(.*)", r"h2. \1", line)
        line = re.sub(r"^\s*#\s+(.*)", r"h1. \1", line)

        # --- Nested Lists ---
        if re.match(r"^(\s*)([\-\*]|\d+\.)\s+", line):
            indent_match = re.match(r"^(\s*)", line)
            indent_level = len(indent_match.group(1)) // 2 + 1

            if re.match(r"^\s*[\-\*]\s+", line):
                content = re.sub(r"^\s*[\-\*]\s+", "", line)
                line = "*" * indent_level + " " + content
            elif re.match(r"^\s*\d+\.\s+", line):
                content = re.sub(r"^\s*\d+\.\s+", "", line)
                line = "#" * indent_level + " " + content

        # --- Task Lists ---
        line = re.sub(r"^\s*[\-\*]\s+\[\s\]\s+", "* ", line)
        line = re.sub(r"^\s*[\-\*]\s+\[x\]\s+", "* (/) ", line)

        # --- Horizontal Rules ---
        line = re.sub(r"^\s*---+\s*$", "----", line)
        line = re.sub(r"^\s*\*\*\*+\s*$", "----", line)

        # --- Inline Formatting ---
        line = re.sub(r"\\(.)", r"\1", line)
        line = re.sub(r"!\[(.*?)\]\((.*?)\)", r"!\2!", line)
        line = re.sub(r"\[(.*?)\]\((.*?)\)", r"[\1|\2]", line)
        line = re.sub(r"\*\*\*(.*?)\*\*\*", r"*_\1_*", line)
        line = re.sub(r"___(.*?)___", r"*_\1_*", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"*\1*", line)
        line = re.sub(r"__(.*?)__", r"*\1*", line)
        line = re.sub(r"(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)", r"_\1_", line)
        line = re.sub(r"(?<!_)_(?!_)(.*?)(?<!_)_(?!_)", r"_\1_", line)
        line = re.sub(r"~~(.*?)~~", r"-\1-", line)
        line = re.sub(r"`(.*?)`", r"{{\1}}", line)
        line = re.sub(r"  $", r"\\\\", line)

        converted_lines.append(line)

    # Handle end-of-file states
    if in_quote_block:
        converted_lines.append("{quote}")
        converted_lines.extend(quote_lines)
        converted_lines.append("{quote}")
    if in_code_block and not in_fenced_code:
        converted_lines.append("{code}")

    return "\n".join(converted_lines)


def convert_v3(markdown_text: str) -> dict[str, Any]:
    """
    Converts Markdown to JIRA API v3 format (Atlassian Document Format - ADF).

    Supports:
    - Headings (H1-H6)
    - Text formatting (bold, italic, strikethrough, inline code)
    - Lists (ordered, unordered, nested)
    - Links and images
    - Code blocks with language support
    - Blockquotes
    - Tables
    - Horizontal rules
    - Line breaks and paragraphs

    Args:
        markdown_text: The markdown string to convert

    Returns:
        Dict representing ADF document structure

    Raises:
        ValueError: If markdown_text is not a string
    """
    if not isinstance(markdown_text, str):
        raise ValueError("markdown_text must be a string")

    if not markdown_text.strip():
        return {"version": 1, "type": "doc", "content": []}

    # Initialize ADF document structure
    doc = {"version": 1, "type": "doc", "content": []}

    # Helper functions
    def text_node(value: str, marks: list[dict] | None = None) -> dict[str, Any]:
        """Create a text node with optional formatting marks."""
        if not value:
            return {"type": "text", "text": ""}
        node = {"type": "text", "text": value}
        if marks:
            node["marks"] = marks
        return node

    def paragraph_node(content: list[dict]) -> dict[str, Any]:
        """Create a paragraph node."""
        return {"type": "paragraph", "content": content or [text_node("")]}

    def hardbreak_node() -> dict[str, Any]:
        """Create a hard break node."""
        return {"type": "hardBreak"}

    # State tracking
    in_code_block = False
    code_lines = []
    code_language = None
    current_list_stack = []  # Stack for nested lists
    current_table = None
    current_blockquote = None

    # Split into lines but preserve line ending information
    lines = markdown_text.split("\n")

    def finalize_contexts(keep_lists: bool = False):
        """Helper to finalize contexts."""
        nonlocal current_table, current_blockquote, current_list_stack
        if not keep_lists:
            current_list_stack = []
        current_table = None
        current_blockquote = None

    def get_list_indent_level(line: str) -> int:
        """Get the indentation level for list items."""
        match = re.match(r"^(\s*)", line)
        return len(match.group(1)) if match else 0

    def process_inline_formatting(text: str) -> list[dict[str, Any]]:
        """Process inline markdown formatting."""
        if not text:
            return [text_node("")]

        # Handle line breaks (two spaces at end of line)
        if text.endswith("  "):
            text = text.rstrip()
            has_break = True
        else:
            has_break = False

        content = []

        # Complex regex to capture all inline formatting
        # Order matters: code first (to avoid processing markdown inside code)
        pattern = r"(`[^`]+`|```[^`]*```|\*\*\*([^*]+)\*\*\*|___([^_]+)___|~~([^~]+)~~|\*\*([^*]+)\*\*|__([^_]+)__|[*_]([^*_]+)[*_]|\[([^\]]+)\]\(([^)]+)\)|!\[([^\]]*)\]\(([^)]+)\))"

        last_end = 0
        for match in re.finditer(pattern, text):
            # Add any text before this match
            if match.start() > last_end:
                plain_text = text[last_end : match.start()]
                if plain_text:
                    content.append(text_node(plain_text))

            full_match = match.group(0)

            # Inline code (highest priority)
            if full_match.startswith("`") and full_match.endswith("`"):
                code_text = full_match[1:-1]
                content.append(text_node(code_text, [{"type": "code"}]))

            # Bold + Italic
            elif full_match.startswith(("***", "___")):
                inner_text = match.group(2) or match.group(3)
                content.append(
                    text_node(inner_text, [{"type": "strong"}, {"type": "em"}])
                )

            # Strikethrough
            elif full_match.startswith("~~"):
                inner_text = match.group(4)
                content.append(text_node(inner_text, [{"type": "strike"}]))

            # Bold
            elif full_match.startswith(("**", "__")):
                inner_text = match.group(5) or match.group(6)
                content.append(text_node(inner_text, [{"type": "strong"}]))

            # Italic
            elif (full_match.startswith("*") and full_match.endswith("*")) or (
                full_match.startswith("_") and full_match.endswith("_")
            ):
                inner_text = match.group(7)
                content.append(text_node(inner_text, [{"type": "em"}]))

            # Links
            elif full_match.startswith("[") and "](" in full_match:
                link_text = match.group(8)
                link_url = match.group(9)
                content.append(
                    text_node(
                        link_text, [{"type": "link", "attrs": {"href": link_url}}]
                    )
                )

            # Images (skip for inline processing, handle separately)
            elif full_match.startswith("!["):
                content.append(text_node(full_match))  # Keep as text for now

            last_end = match.end()

        # Add any remaining text
        if last_end < len(text):
            remaining_text = text[last_end:]
            if remaining_text:
                content.append(text_node(remaining_text))

        # Add hard break if line ended with two spaces
        if has_break:
            content.append(hardbreak_node())

        return content if content else [text_node(text)]

    i = 0
    while i < len(lines):
        line = lines[i]

        # Handle empty lines
        if re.match(r"^\s*$", line):
            # Empty lines break most contexts except tables
            if current_blockquote:
                finalize_contexts()
            i += 1
            continue

        # Code blocks (must be checked before other patterns)
        code_match = re.match(r"^```(\w*)", line)
        if code_match:
            if in_code_block:
                # End of code block
                code_content = "\n".join(code_lines)
                code_block = {"type": "codeBlock", "content": [text_node(code_content)]}
                if code_language:
                    code_block["attrs"] = {"language": code_language}

                doc["content"].append(code_block)
                code_lines = []
                code_language = None
                in_code_block = False
            else:
                # Start of code block
                finalize_contexts()
                in_code_block = True
                code_language = code_match.group(1) or None
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            finalize_contexts()
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2)
            doc["content"].append(
                {
                    "type": "heading",
                    "attrs": {"level": level},
                    "content": process_inline_formatting(heading_text),
                }
            )
            i += 1
            continue

        # Horizontal rules
        if re.match(r"^(\*{3,}|-{3,}|_{3,})\s*$", line):
            finalize_contexts()
            doc["content"].append({"type": "rule"})
            i += 1
            continue

        # Lists with nested support
        list_match = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)", line)
        if list_match:
            indent = get_list_indent_level(line)
            list_type = (
                "orderedList"
                if list_match.group(2).rstrip().endswith(".")
                else "bulletList"
            )
            item_content = list_match.group(3)

            # Clear non-list contexts
            current_table = None
            current_blockquote = None

            # Determine list depth
            target_depth = indent // 2  # Assuming 2 spaces per indent level

            # Adjust list stack to match target depth
            while len(current_list_stack) > target_depth + 1:
                current_list_stack.pop()

            # Create new list if needed
            if len(current_list_stack) <= target_depth:
                new_list = {"type": list_type, "content": []}

                if current_list_stack:
                    # Add to parent list item
                    parent_item = current_list_stack[-1]["content"][-1]
                    if "content" not in parent_item:
                        parent_item["content"] = []
                    parent_item["content"].append(new_list)
                else:
                    # Add to document
                    doc["content"].append(new_list)

                current_list_stack.append(new_list)

            # Add list item
            current_list = current_list_stack[-1]
            list_item = {
                "type": "listItem",
                "content": [paragraph_node(process_inline_formatting(item_content))],
            }
            current_list["content"].append(list_item)
            i += 1
            continue

        # Blockquotes
        blockquote_match = re.match(r"^>\s*(.*)", line)
        if blockquote_match:
            if not current_blockquote:
                finalize_contexts(keep_lists=False)
                current_blockquote = {"type": "blockquote", "content": []}
                doc["content"].append(current_blockquote)

            quote_content = blockquote_match.group(1)
            current_blockquote["content"].append(
                paragraph_node(process_inline_formatting(quote_content))
            )
            i += 1
            continue

        # Tables - check for separator row first
        if "|" in line:
            # Check if this is a table separator row (e.g., | ---- | ---- |)
            if re.match(r"^\s*\|?\s*[-:|]+(\s*\|\s*[-:|]+)*\s*\|?\s*$", line):
                # This is a separator row, skip it but don't break table context
                i += 1
                continue

            # This is a table content row
            if not current_table:
                finalize_contexts()
                current_table = {"type": "table", "content": []}
                doc["content"].append(current_table)

            # Parse table row
            # Handle edge cases with pipes
            line_content = line.strip()
            line_content = line_content.removeprefix("|")
            line_content = line_content.removesuffix("|")

            parts = line_content.split("|")
            cells = [part.strip() for part in parts]

            if cells and any(
                cell for cell in cells
            ):  # Only create row if we have non-empty content
                row = {"type": "tableRow", "content": []}
                current_table["content"].append(row)
                for cell in cells:
                    row["content"].append(
                        {
                            "type": "tableCell",
                            "content": [
                                paragraph_node(process_inline_formatting(cell))
                            ],
                        }
                    )
            i += 1
            continue

        # Images (standalone)
        image_match = re.match(r"^!\[(.*?)\]\((.*?)\)(?:\s+\"(.*?)\")?\s*$", line)
        if image_match:
            finalize_contexts()
            alt_text = image_match.group(1)
            image_url = image_match.group(2)
            title = image_match.group(3)

            media_attrs = {"type": "external", "url": image_url}
            if alt_text:
                media_attrs["alt"] = alt_text
            if title:
                media_attrs["title"] = title

            doc["content"].append(
                {
                    "type": "mediaGroup",
                    "content": [{"type": "media", "attrs": media_attrs}],
                }
            )
            i += 1
            continue

        # Break contexts if we're in a non-continuing context
        if (
            current_blockquote
            and not line.startswith(">")
            or current_table
            and "|" not in line
        ):
            finalize_contexts()
        elif current_list_stack and not re.match(r"^(\s*)([-*+]|\d+\.)", line):
            current_list_stack = []

        # Default: paragraph with inline formatting
        if line.strip():
            formatted_content = process_inline_formatting(line)
            doc["content"].append(paragraph_node(formatted_content))

        i += 1

    # Handle any remaining code block
    if in_code_block and code_lines:
        code_content = "\n".join(code_lines)
        code_block = {"type": "codeBlock", "content": [text_node(code_content)]}
        if code_language:
            code_block["attrs"] = {"language": code_language}
        doc["content"].append(code_block)

    return doc


# # --- Example Usage ---
# if __name__ == "__main__":
#     fname = "/tmp/a.md"
#     with open(fname, "r") as f:
#         md = f.read()
#         print("Markdown to JIRA conversion:")
#         print(convert(md))
