import os


def load_template(jayrah_obj, template_name):
    """Load issue template from config (by type, string or file), user templates dir, or repository."""
    config_templates = jayrah_obj.config.get("templates", {})
    # 1. Check local templates in config (by type)
    if template_name and template_name.lower() in config_templates:
        val = config_templates[template_name.lower()]
        # If it's a string and a valid file path, load the file
        if isinstance(val, str) and os.path.isfile(os.path.expanduser(val)):
            with open(os.path.expanduser(val), "r") as f:
                return f.read()
        # Otherwise, treat as inline template
        return val
    # 2. Check ~/.config/jayrah/templates/{type}.md
    if template_name:
        user_template_path = os.path.expanduser(
            f"~/.config/jayrah/templates/{template_name.lower()}.md"
        )
        if os.path.isfile(user_template_path):
            with open(user_template_path, "r") as f:
                return f.read()
    # 3. Check repository templates
    repo_template = find_repo_template(template_name)
    if repo_template:
        return repo_template
    return None


def find_repo_template(template_name):
    """Find template in repository."""
    # Look for templates in .github/ISSUE_TEMPLATE/ or .jira/templates/
    template_paths = [
        ".github/ISSUE_TEMPLATE/",
        ".jira/templates/",
        ".templates/",
    ]

    for path in template_paths:
        if os.path.exists(path):
            template_file = os.path.join(path, f"{template_name}.md")
            if os.path.exists(template_file):
                with open(template_file, "r") as f:
                    return f.read()

    return None
