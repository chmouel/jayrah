"""Create command for Jayrah Jira CLI."""

import os

import click

from ..create.create import create_edit_issue, interactive_create
from .common import cli
from .completions import ComponentType, IssueType, PriorityType


@cli.command("create")
@click.option("--type", "-T", "issuetype", help="Issue type", type=IssueType())
@click.option("--title", "-t", "title", help="Issue title/summary")
@click.option("--body", "-b", "body", help="Issue description")
@click.option(
    "--body-file",
    "-F",
    "body_file",
    type=click.Path(exists=True),
    help="Read description from file",
)
@click.option(
    "--priority", "-p", "priority", help="Issue priority", type=PriorityType()
)
@click.option("--assignee", "-a", "assignee", help="Issue assignee")
@click.option("--labels", "-l", "labels", multiple=True, help="Issue labels")
@click.option(
    "--components",
    "-c",
    "components",
    multiple=True,
    help="Issue components",
    type=ComponentType(),
)
@click.option(
    "--dry-run",
    "-n",
    "dry_run",
    is_flag=True,
    help="Preview the issue without creating it",
)
@click.option("--template", "-T", "template", help="Use a specific template")
@click.pass_obj
def create(
    jayrah_obj,
    issuetype,
    title,
    body,
    body_file,
    priority,
    assignee,
    labels,
    template,
    components,
    dry_run,
):
    """Create an issue"""
    if body_file:
        if not os.path.exists(body_file):
            raise FileNotFoundError(f"{body_file} does not exist")

        with open(body_file, "r") as f:
            body = f.read()

    if jayrah_obj.config.get("create"):
        if not issuetype and jayrah_obj.config["create"].get("type"):
            issuetype = jayrah_obj.config["create"]["type"]
        if not components and jayrah_obj.config["create"].get("components"):
            components = jayrah_obj.config["create"]["components"]
        if not labels and jayrah_obj.config["create"].get("labels"):
            labels = jayrah_obj.config["create"]["labels"]
        if not assignee and jayrah_obj.config["create"].get("assignee"):
            assignee = jayrah_obj.config["create"]["assignee"]
        if not priority and jayrah_obj.config["create"].get("priority"):
            priority = jayrah_obj.config["create"]["priority"]

    defaults = create_edit_issue(
        jayrah_obj,
        title,
        issuetype,
        template=template,
        body=body,
        labels=labels,
        components=components,
        assignee=assignee,
        priority=priority,
    )

    # Create the issue
    interactive_create(jayrah_obj, defaults, dry_run=dry_run)
