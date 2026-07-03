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
from mcp_gnu_units.engine import UnitsError, database_version, get_database
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
                raise ToolError(format_validation_error(name, exc.__cause__)) from exc.__cause__
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

    Returns seven keys: `status` ("available"), `name`, `version` (package version),
    `python` (runtime version), `mcp_sdk` (MCP SDK version, or "unknown"),
    `toolsets` (empty until the GNU units engine lands), and `units_db` — the
    bundled GNU units database's `source`, `data_version`, and `data_updated`
    (§2.4.6 / §5.4), read from the shipped file's own header so it can't drift.
    Example: {"status":"available","name":"mcp-gnu-units","version":"0.0.1",
    "python":"3.12.3","mcp_sdk":"1.28.0","toolsets":[],
    "units_db":{"source":"GNU units","data_version":"3.26","data_updated":"2026-02-25"}}
    """
    try:  # metadata may be absent (uninstalled SDK); never crash info()
        mcp_sdk = version("mcp")
    except PackageNotFoundError:
        mcp_sdk = "unknown"
    try:  # header parse is cheap + best-effort; never crash info()
        units_db = database_version()
    except Exception:  # noqa: BLE001 - version reporting must not break health check
        units_db = {"source": "GNU units"}
    return {
        "status": "available",
        "name": "mcp-gnu-units",
        "version": __version__,
        "python": platform.python_version(),
        "mcp_sdk": mcp_sdk,
        "toolsets": [],  # placeholder; filled when the engine lands (§5.4 / §2.4)
        "units_db": units_db,
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
    a list of objects each carrying:
      - `name`       : the unit's name.
      - `definition` : its definition text (the source line with the leading
                       name token removed, so the name is not repeated).
      - `kind`       : "unit" | "primitive" | "function" | "table".
      - `dimension`  : the unit reduced to base-unit signature, e.g. "kg m^2 / s^3"
                       for power — use it to check whether two units are
                       conformable without a second call. Omitted for hits that
                       do not reduce (functions, tables).
      - `base_value` : the unit reduced to base/primitive units, coefficient
                       included, e.g. "745.699 kg m^2 / s^3". Omitted alongside
                       `dimension` when the hit does not reduce.
    Enriching each hit lets you search AND triage in a single call instead of a
    follow-up lookup per unit.
    Example: find_units("horsepower") ->
    {"query":"horsepower","count":9,"results":[{"name":"horsepower",
    "definition":"550 foot pound force / sec","kind":"unit",
    "dimension":"kg m^2 / s^3","base_value":"745.7 kg m^2 / s^3"}, ...]}
    """
    db = get_database()
    results = [db.describe(name) for name, _ in db.find_units(query, limit=limit)]
    return {"query": query, "count": len(results), "results": results}


@mcp.tool()
def convert(
    from_expr: Annotated[
        str,
        Field(
            description=(
                "The quantity or unit expression to convert FROM. May carry a numeric "
                "coefficient and be a compound expression: '2.5 acre*ft', '55 mile/hour', "
                "'kW*h', '0 tempC'. A bare unit like 'mile' is treated as one of that unit."
            ),
            min_length=1,
        ),
    ],
    to_expr: Annotated[
        str,
        Field(
            description=(
                "The unit expression to convert TO, e.g. 'km', 'gallons', 'joule', "
                "'tempF'. Must be dimensionally conformable with `from_expr` (both length, "
                "both energy, …) or a nonlinear target such as 'tempF'; otherwise the call "
                "errors. Use find_units to discover the exact spelling of a unit."
            ),
            min_length=1,
        ),
    ],
) -> dict:
    """Convert a value or unit expression from one unit to another (GNU units engine, TODO §16).

    The universal conversion core: one tool covers every category (length, mass,
    time, temperature, area, volume, energy, power, speed, data, …) plus compound
    expressions like `kW*h` or `acre*ft`. Linear conversions return the ratio of
    coefficients; a nonlinear target (e.g. `tempF`) applies that unit's inverse.

    Returns: `from` and `to` (echoed), `result` (the converted magnitude WITH the
    target unit, e.g. "1.609344 km" — the primary human-readable answer), `value`
    (the same magnitude as a bare float for programmatic use), and `exact` (true
    when the result is exact, false when it was rounded).
    Errors cleanly (isError) when a unit is unknown, an expression is malformed,
    or the two sides are not conformable.
    Example: convert("1 mile", "km") ->
    {"from":"1 mile","to":"km","result":"1.609344 km","value":1.609344,"exact":true}
    """
    db = get_database()
    try:
        res = db.convert(from_expr, to_expr)
    except UnitsError as exc:
        raise ToolError(str(exc)) from exc
    return {
        "from": from_expr,
        "to": to_expr,
        "result": f"{res.formatted} {to_expr}",
        "value": res.value.as_float(),
        "exact": res.exact,
    }


# TODO §4.5 / FUTURE — remaining domain tools backed by the GNU units engine
#           (convert_to_si, define_unit, list_prefixes). find_units landed per
#           §14.1, convert per §16.1; the rest follow.
#           info() reports the bundled GNU units database version it ships via
#           `units_db` (§2.4.6 / §5.4).
