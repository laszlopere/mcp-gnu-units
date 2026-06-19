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

from collections.abc import Sequence as AbcSequence
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ContentBlock
from pydantic import ValidationError

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
#
# TODO §5 — the skeleton's one tool: `info()` (availability + version report).
#           Register it here next.
#
# TODO §4.5 / FUTURE — domain tools backed by the GNU units engine
#           (convert, convert_to_si, find_units, define_unit, list_prefixes).
#           Built only after section 9 is green; nothing registered here yet.
