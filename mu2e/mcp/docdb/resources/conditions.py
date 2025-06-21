"""Experiment conditions resource for MCP server."""

import os


def get_experiment_conditions() -> dict:
    """Get the current experiment conditions."""
    return {
        "experiment": {
            "status": "construction",
            "mood": "good",
            "pwd": os.getcwd()
        }
    }