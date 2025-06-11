"""
Converts Markdown to JIRA markup language.
Handles headings, formatting, lists, links, code, blockquotes, tables, images, etc.
"""

import re


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


# # --- Example Usage ---
# if __name__ == "__main__":
#     fname = "/tmp/a.md"
#     with open(fname, "r") as f:
#         md = f.read()
#         print("Markdown to JIRA conversion:")
#         print(convert(md))
