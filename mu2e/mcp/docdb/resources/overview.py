"""Overview resource for MCP server."""

import os


def get_mu2e_overview() -> str:
    """Get the Mu2e overview information."""
    return "Mu2e is an awesome experiment." + os.environ['MU2E_DOCDB_USERNAME']