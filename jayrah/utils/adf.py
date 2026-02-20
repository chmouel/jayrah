"""Utilities for handling Atlassian Document Format (ADF)."""

import json


def extract_text_from_adf(adf_data):
    """Extract plain text from Atlassian Document Format (ADF).

    This is a simple implementation that extracts text content from ADF JSON.
    For more complex ADF handling, a more robust parser would be needed.

    Args:
        adf_data: ADF data as a dictionary or JSON string

    Returns:
        Extracted plain text as a string
    """
    if isinstance(adf_data, str):
        try:
            adf_data = json.loads(adf_data)
        except json.JSONDecodeError:
            # If it's not valid JSON, return as is
            return adf_data

    if not isinstance(adf_data, dict):
        # If it's not a dictionary, return as string
        return str(adf_data)

    # Check if it's ADF format with content
    if "content" not in adf_data:
        return str(adf_data)

    # Extract text recursively
    text_parts = []

    def extract_text(node):
        if isinstance(node, dict):
            if node.get("type") == "text" and "text" in node:
                text_parts.append(node["text"])
            elif "content" in node and isinstance(node["content"], list):
                for child in node["content"]:
                    extract_text(child)
        elif isinstance(node, list):
            for item in node:
                extract_text(item)

    extract_text(adf_data)
    return "\n".join(text_parts)


def create_adf_from_text(text):
    """Create a simple ADF document from plain text.

    Args:
        text: Plain text string

    Returns:
        ADF document as a dictionary
    """
    # Split text into paragraphs
    paragraphs = text.split("\n\n")

    # Create content array with paragraph nodes
    content = []
    for para in paragraphs:
        if not para.strip():
            continue

        # Split paragraph into lines for multiple text nodes
        lines = para.split("\n")

        para_content = [
            {"type": "text", "text": line} for line in lines if line.strip()
        ]

        if para_content:
            content.append({"type": "paragraph", "content": para_content})

    # Create the document structure
    return {"type": "doc", "version": 1, "content": content}
