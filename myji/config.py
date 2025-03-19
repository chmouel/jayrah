import pathlib

import click
import yaml
from rich.prompt import Prompt

from myji import utils

from . import defaults


def make_config(config: dict, config_file: pathlib.Path) -> dict:
    config = read_config(config, pathlib.Path(config_file))
    # Check for missing credentials and prompt if needed
    config_modified = False
    config_path = pathlib.Path(config_file)

    if not config["jira_server"]:
        config["jira_server"] = Prompt.ask("Enter Jira server URL")
        config_modified = True

    if not config["jira_user"]:
        config["jira_user"] = Prompt.ask("Enter Jira username")
        config_modified = True

    if not config["jira_project"]:
        config["jira_project"] = Prompt.ask("Enter your Jira Component (ie: SRVKP)")
        config_modified = True

    if not config["jira_password"]:
        config["jira_password"] = Prompt.ask(
            "Enter your Jira password (or token)", password=True
        )
        config_modified = True

    # Ensure server URL has https:// prefix
    if config["jira_server"] and not config["jira_server"].startswith("https://"):
        config["jira_server"] = "https://" + config["jira_server"]
        config_modified = True

    if "boards" not in config:
        config["boards"] = defaults.BOARDS

    # Save the config if modified
    if config_modified:
        write_config(config, config_path)
        click.echo(f"Configuration saved to {config_file}", err=True)

    return config


def read_config(ret: dict, config_file: pathlib.Path) -> dict:
    """Read configuration from yaml file"""

    def checks():
        if ret["jira_server"] and not ret["jira_server"].startswith("https://"):
            ret["jira_server"] = "https://" + ret["jira_server"]

        if (
            "jira_password" in ret
            and ret["jira_password"]
            and ret["jira_password"].startswith("pass::")
        ):
            ret["jira_password"] = utils.get_pass_key(
                ret["jira_password"].split("::")[-1]
            )

        if "cache_ttl" not in ret or ret["cache_ttl"] is None:
            ret["cache_ttl"] = defaults.CACHE_DURATION

        if "boards" not in ret:
            ret["boards"] = defaults.BOARDS

    checks
    if not config_file.exists():
        return ret

    with config_file.open() as file:
        config = yaml.safe_load(file)
        if config.get("general"):
            general = config["general"]

            def set_general(x):
                return general.get(x) if x in general and general.get(x) else None

            for x in [
                "jira_server",
                "jira_user",
                "jira_password",
                "jira_component",
                "jira_project",
                "cache_ttl",
            ]:
                ret[x] = set_general(x)
        if config.get("boards"):
            ret["boards"] = config["boards"]
    checks()
    return ret


def write_config(config, config_file: pathlib.Path):
    """Write configuration to yaml file"""
    # Create config directory if it doesn't exist
    config_file.parent.mkdir(parents=True, exist_ok=True)

    # Prepare the config structure
    yaml_config = {"general": {}}
    for key in [
        "jira_server",
        "jira_user",
        "jira_password",
        "jira_component",
        "cache_ttl",
    ]:
        if config.get(key):
            yaml_config["general"][key] = config[key]

    # Write to file
    with config_file.open("w") as file:
        yaml.safe_dump(yaml_config, file)
