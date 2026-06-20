# mcp-gnu-units — pure-Python MCP server for GNU units conversion & dimensional analysis.
# Copyright (C) 2026  Laszlo Pere
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""FastMCP application singleton — all tools register against this `mcp` app.

Transport is stdio (FastMCP default), which is what Claude Code / Desktop launch
(TODO §4.4). No HTTP/SSE in the skeleton.
"""

import platform
from collections.abc import Sequence as AbcSequence
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ContentBlock
from pydantic import Field, ValidationError

from mcp_gnu_units import __version__
from mcp_gnu_units.engine import get_database
from mcp_gnu_units.errors import format_validation_error


class _GnuUnitsFastMCP(FastMCP):
    """FastMCP that reshapes argument-validation errors for the model (TODO §4.6.3).

    FastMCP wraps a failed pydantic argument validation as a ToolError whose
    `__cause__` is the ValidationError. We catch that one case and re-raise with
    a concise, field-naming message (errors.format_validation_error); the SDK
    still returns it as an `isError` result. Tool-body failures (a tool's own
    ValueError, etc.) carry a different cause or none, so they fall through
    unchanged.
    """

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> AbcSequence[ContentBlock] | dict[str, Any]:
        try:
            return await super().call_tool(name, arguments)
        except ToolError as exc:
            if isinstance(exc.__cause__, ValidationError):
                raise ToolError(
                    format_validation_error(name, exc.__cause__)
                ) from exc.__cause__
            raise


# TODO §4.1 — the singleton app. Every tool registers here.
mcp = _GnuUnitsFastMCP(
    "mcp-gnu-units",
    instructions=(
        "Precise, offline unit conversion and dimensional analysis backed by the "
        "GNU units database: convert between 3000+ units, evaluate compound unit "
        "expressions, and search/define units. Deterministic and local."
    ),
)

# Tools register below.


@mcp.tool()
def info() -> dict:
    """Discovery / health-check entrypoint: report availability and version info.

    Returns six keys: `status` ("available"), `name`, `version` (package version),
    `python` (runtime version), `mcp_sdk` (MCP SDK version, or "unknown"), and
    `toolsets` (empty until the GNU units engine lands).
    Example: {"status":"available","name":"mcp-gnu-units","version":"0.0.1",
    "python":"3.12.3","mcp_sdk":"1.28.0","toolsets":[]}
    """
    try:  # metadata may be absent (uninstalled SDK); never crash info()
        mcp_sdk = version("mcp")
    except PackageNotFoundError:
        mcp_sdk = "unknown"
    return {
        "status": "available",
        "name": "mcp-gnu-units",
        "version": __version__,
        "python": platform.python_version(),
        "mcp_sdk": mcp_sdk,
        "toolsets": [],  # placeholder; filled when the engine lands (§5.4 / §2.4)
    }


@mcp.tool()
def find_units(
    query: Annotated[
        str,
        Field(
            description=(
                "Case-insensitive substring to search for. Matches against both the "
                "unit NAME and its DEFINITION text, so 'meter' finds the `meter` unit "
                "itself as well as units defined in terms of it (e.g. `micron`). Use a "
                "short keyword like 'byte', 'pressure', or 'newton'."
            ),
            min_length=1,
        ),
    ],
    limit: Annotated[
        int,
        Field(
            description=(
                "Maximum number of matches to return (results are in the database's "
                "native definition order; the scan stops once this many are found)."
            ),
            ge=1,
            le=500,
        ),
    ] = 50,
) -> dict:
    """Search the GNU units database for units whose name or definition contains a keyword.

    Basic substring search over the 3000+ unit GNU units database (TODO §14.1). A
    hit is any unit whose name OR definition text contains `query` (case-insensitive);
    prefixes are excluded. Results are returned in the database's native order and
    capped at `limit`. Use this to discover the exact spelling of a unit before
    calling a conversion tool.

    Returns: `query` (echoed), `count` (number of results returned), and `results`,
    a list of {`name`, `definition`} objects where `definition` is the unit's raw
    source line from the database.
    Example: find_units("meter") ->
    {"query":"meter","count":50,"results":[{"name":"meter","definition":"meter     m"},
    {"name":"LENGTH","definition":"LENGTH                  meter"}, ...]}
    """
    hits = get_database().find_units(query, limit=limit)
    results = [{"name": name, "definition": definition} for name, definition in hits]
    return {"query": query, "count": len(results), "results": results}


# TODO §4.5 / FUTURE — remaining domain tools backed by the GNU units engine
#           (convert, convert_to_si, define_unit, list_prefixes). find_units
#           landed per §14.1; the rest follow.
#           When the engine version is surfaced, info() also reports the bundled
#           GNU units database version it ships (§2.4 / §5.4).
