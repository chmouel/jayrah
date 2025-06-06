"""Cache management command for Jayrah Jira CLI."""

import sys
import time

import click

from ..api import jira as jirahttp
from ..utils import log
from .common import cli


@cli.command(name="cache")
@click.option("--clear", is_flag=True, help="Clear the cache")
@click.option("--prune", is_flag=True, help="Prune expired cache entries")
@click.option(
    "--max-age", type=int, help="Maximum age of cache entries in seconds (for pruning)"
)
@click.pass_obj
def cache_command(jayrah_obj, clear, prune, max_age):
    """Manage jayrah cache."""

    config = jayrah_obj.config
    jira = jirahttp.JiraHTTP(config)

    if clear:
        jira.cache.clear()
        log("Cache cleared")
        return

    if prune:
        pruned_count = jira.cache.prune(max_age)
        log(f"Pruned {pruned_count} cache entries")
        return

    if not clear and not prune:
        cache_stats = jira.get_cache_stats()

        if "error" in cache_stats:
            log(f"Error getting cache stats: {cache_stats['error']}")
            sys.exit(1)

        log("Cache Statistics:")
        log(f"  Entries: {cache_stats['entries']}")
        log(f"  Size: {cache_stats['size_mb']} MB")
        log(f"  Database Path: {cache_stats['db_path']}")
        log(f"  Cache TTL: {cache_stats['cache_ttl']} seconds")
        log(f"  Serialization: {cache_stats.get('serialization', 'pickle')}")

        if cache_stats.get("oldest_entry"):
            oldest_time = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(cache_stats["oldest_entry"])
            )
            log(f"  Oldest Entry: {oldest_time}")

        if cache_stats.get("newest_entry"):
            newest_time = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(cache_stats["newest_entry"])
            )
            log(f"  Newest Entry: {newest_time}")

        return
