"""Shared fixtures for engine tests (TODO §2.4.8)."""

import pytest

from mcp_gnu_units.engine.loader import load


@pytest.fixture(scope="session")
def symbols():
    """The full bundled database, loaded once under the default configuration."""
    return load()
