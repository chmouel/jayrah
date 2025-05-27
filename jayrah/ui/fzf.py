import subprocess
from typing import List, Optional, Union


def fzf_select(
    prompt: str,
    options: List[str],
    multi: bool = False,
    default: Optional[str] = None,
) -> Union[str, List[str]]:
    """
    Use fzf to select from a list of options.

    Args:
        prompt: The prompt to display
        options: List of options to choose from
        multi: Whether to allow multiple selections
        default: Default value to use if provided

    Returns:
        Selected option(s) as string or list of strings
    """
    if not options:
        return [] if multi else None

    # If there's only one option and no default, return it
    if len(options) == 1 and not default:
        return options[0] if not multi else options

    # Prepare fzf command
    cmd = ["fzf", "--prompt", f"{prompt}> "]

    # Add multi-select if requested
    if multi:
        cmd.extend(["--multi"])

    # Add default value if provided
    if default:
        cmd.extend(["--query", default])

    try:
        # Run fzf with the options as input
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate(input="\n".join(options))

        if process.returncode == 0 and stdout:
            # For multi-select, return a list of selected items
            if multi:
                return [line.strip() for line in stdout.splitlines()]
            # For single select, return the selected item
            return stdout.strip()
        return None
    except subprocess.CalledProcessError:
        return None
    except FileNotFoundError:
        raise RuntimeError("fzf is not installed. Please install it first.")
