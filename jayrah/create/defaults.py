"""Default values and helpers for Jayrah issue creation."""

issue_template = """---
title: {title}
type: {issuetype}
components: {components}
labels: {labels}
assignee: {assignee}
priority: {priority}
---
{content}"""

default_content = """## Description

Please provide a clear and concise description of the issue or feature.

## Steps to Reproduce (for bugs)

1. Step one
2. Step two
3. ...

## Expected Behavior

Describe what you expected to happen.

## Actual Behavior

Describe what actually happened.

## Acceptance Criteria (for stories/features)

- [ ] Clearly defined acceptance criterion
- [ ] ...

## Additional Information

Add any other context, screenshots, or information here.
"""
