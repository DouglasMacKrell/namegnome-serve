"""CLI entrypoints for NameGnome Serve."""

from namegnome_serve.cli.cache import app as cache_app
from namegnome_serve.cli.plan import app as plan_app

__all__ = ["cache_app", "plan_app"]
