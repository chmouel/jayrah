import click

from .. import utils
from ..config import defaults


class Issues:
    def __init__(self, config: dict, jira):
        self.jira = jira
        self.config = config
        self.verbose = self.config.get("verbose", False)

    # pylint: disable=too-many-positional-arguments
    def list_issues(
        self,
        jql,
        order_by="updated",
        limit=100,
        all_pages=True,
        fields=None,
        start_at=None,
        use_cache=True,
    ):
        """List issues using JQL query."""
        # Handle the dangerous default value
        if fields is None:
            fields = list(defaults.FIELDS)  # Create a copy of the default list

        if self.verbose:
            click.echo(f"Listing issues with JQL: {jql}", err=True)
            click.echo(
                f"Order by: {order_by}, Limit: {limit}, All pages: {all_pages}, Cache: {use_cache}",
                err=True,
            )
            click.echo(f"Fields: {fields}", err=True)

        issues = []
        current_start_at = 0 if start_at is None else start_at
        while True:
            if self.verbose:
                click.echo(f"Fetching batch starting at {current_start_at}", err=True)

            result = self.jira.search_issues(
                jql,
                start_at=current_start_at,
                max_results=limit,
                fields=fields,
                use_cache=use_cache,
            )

            batch_issues = result.get("issues", [])
            issues.extend(batch_issues)

            if self.verbose:
                utils.log(
                    f"Retrieved {len(batch_issues)} issues (total: {len(issues)})",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )

            total = result.get("total", 0)
            if not all_pages or current_start_at + limit >= total:
                break

            current_start_at += limit

        return issues
