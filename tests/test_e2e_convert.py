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

"""§16.2 — end-to-end golden pins for the `convert` tool, exercised through the
FastMCP layer (`mcp.call_tool`), same path a real client drives.

Two ways to run it:
  * as part of the suite — `uv run pytest` collects `test_e2e_convert` below;
  * as a standalone script — `python tests/test_e2e_convert.py`:
        (no options)       print only the pass/fail statistics
        --verbose          also print each request/reply as JSON
        --human-readable   also print each conversion in a readable line
"""

import argparse
import asyncio
import json
import sys

from mcp.server.fastmcp.exceptions import ToolError

from mcp_gnu_units.server import mcp

# Golden conversions with pinned answers. `expect` cases must succeed and every
# listed field must match; `error` cases must raise a ToolError containing the
# substring. Values were pinned against the tool's real output, not hand-computed.
GOLDEN: list[dict] = [
    # -- linear conversions across categories -----------------------------
    {
        "args": {"from_expr": "1 mile", "to_expr": "km"},
        "expect": {"result": "1.609344 km", "value": 1.609344, "exact": True},
    },
    {
        "args": {"from_expr": "1 inch", "to_expr": "cm"},
        "expect": {"result": "2.54 cm", "value": 2.54, "exact": True},
    },
    {
        "args": {"from_expr": "1 ft", "to_expr": "m"},
        "expect": {"result": "0.3048 m", "value": 0.3048, "exact": True},
    },
    {
        "args": {"from_expr": "1 lb", "to_expr": "kg"},
        "expect": {"result": "0.45359237 kg", "exact": True},
    },
    {
        "args": {"from_expr": "1 gallon", "to_expr": "liter"},
        "expect": {"result": "3.785411784 liter", "exact": True},
    },
    {
        "args": {"from_expr": "1 hour", "to_expr": "s"},
        "expect": {"result": "3600 s", "value": 3600.0, "exact": True},
    },
    {
        "args": {"from_expr": "1 atm", "to_expr": "pascal"},
        "expect": {"result": "101325 pascal", "value": 101325.0, "exact": True},
    },
    {
        "args": {"from_expr": "1 acre", "to_expr": "m^2"},
        "expect": {"result": "4046.8564224 m^2", "exact": True},
    },
    {
        "args": {"from_expr": "60 mph", "to_expr": "km/hour"},
        "expect": {"result": "96.56064 km/hour", "exact": True},
    },
    # -- data units (binary prefixes) -------------------------------------
    {
        "args": {"from_expr": "1 byte", "to_expr": "bit"},
        "expect": {"result": "8 bit", "value": 8.0, "exact": True},
    },
    {
        "args": {"from_expr": "1 GiB", "to_expr": "MiB"},
        "expect": {"result": "1024 MiB", "value": 1024.0, "exact": True},
    },
    # -- compound unit expressions ----------------------------------------
    {
        "args": {"from_expr": "1 kW*hour", "to_expr": "J"},
        "expect": {"result": "3600000 J", "value": 3600000.0, "exact": True},
    },
    {
        "args": {"from_expr": "1 kg m/s^2", "to_expr": "newton"},
        "expect": {"result": "1 newton", "value": 1.0, "exact": True},
    },
    {
        "args": {"from_expr": "1 N m", "to_expr": "joule"},
        "expect": {"result": "1 joule", "value": 1.0, "exact": True},
    },
    # exact ratio whose 12-significant-figure rendering is a rounded decimal:
    # `exact` reports the internal rational, NOT the truncated display string.
    {
        "args": {"from_expr": "2.5 acre*ft", "to_expr": "gallons"},
        "expect": {"result": "814628.571429 gallons", "exact": True},
    },
    # -- inexact result (irrational coefficient) --------------------------
    {
        "args": {"from_expr": "sqrt(2) m", "to_expr": "m"},
        "expect": {"result": "1.41421356237 m", "exact": False},
    },
    # -- function (nonlinear) units, both directions ----------------------
    {
        "args": {"from_expr": "tempC(0)", "to_expr": "tempF"},
        "expect": {"result": "32 tempF", "value": 32.0, "exact": True},
    },
    {
        "args": {"from_expr": "tempC(100)", "to_expr": "tempF"},
        "expect": {"result": "212 tempF", "value": 212.0, "exact": True},
    },
    {
        "args": {"from_expr": "tempF(212)", "to_expr": "tempC"},
        "expect": {"result": "100 tempC", "value": 100.0, "exact": True},
    },
    {
        "args": {"from_expr": "tempF(32)", "to_expr": "tempC"},
        "expect": {"result": "0 tempC", "value": 0.0, "exact": True},
    },
    {
        "args": {"from_expr": "tempC(0)", "to_expr": "K"},
        "expect": {"result": "273.15 K", "value": 273.15, "exact": True},
    },
    # linear source -> nonlinear target (the function's inverse is applied)
    {
        "args": {"from_expr": "300 K", "to_expr": "tempC"},
        "expect": {"result": "26.85 tempC", "value": 26.85, "exact": True},
    },
    # -- piecewise table units, both directions ---------------------------
    {
        "args": {"from_expr": "brwiregauge(0)", "to_expr": "mm"},
        "expect": {"result": "8.2296 mm", "value": 8.2296, "exact": True},
    },
    {
        "args": {"from_expr": "2 mm", "to_expr": "brwiregauge"},
        "expect": {"result": "14.157480315 brwiregauge", "exact": True},
    },
    # -- error paths (each must fail cleanly, not crash) ------------------
    {"args": {"from_expr": "1 meter", "to_expr": "kg"}, "error": "non-conformable"},
    {
        "args": {"from_expr": "1 liter", "to_expr": "meter"},
        "error": "cannot convert '1 liter' to 'meter': non-conformable",
    },
    {
        "args": {"from_expr": "1 foobarunit", "to_expr": "m"},
        "error": "'foobarunit' is not a defined unit",
    },
    {"args": {"from_expr": "1 m", "to_expr": "zzznot"}, "error": "'zzznot' is not a defined unit"},
    # a nonlinear unit used as a bare source needs call syntax, e.g. tempF(50)
    {
        "args": {"from_expr": "50 tempF", "to_expr": "tempC"},
        "error": "'tempF' is not a defined unit",
    },
    # nonlinear/table TARGET with a source of the wrong dimension
    {
        "args": {"from_expr": "1", "to_expr": "brwiregauge"},
        "error": "cannot convert to table 'brwiregauge'",
    },
    {"args": {"from_expr": "1 m", "to_expr": "tempF"}, "error": "non-conformable"},
]


def _call(args: dict) -> tuple[str, object]:
    """Invoke `convert` through the app; return ('ok', payload) or ('error', message)."""

    async def go():
        return await mcp.call_tool("convert", args)

    try:
        result = asyncio.run(go())
    except ToolError as exc:
        return "error", str(exc)
    contents = result[0] if isinstance(result, tuple) else result
    return "ok", json.loads(contents[0].text)


def _check(case: dict) -> tuple[bool, str, tuple[str, object]]:
    """Run one golden case. Return (passed, reason, (status, reply))."""
    status, reply = _call(case["args"])
    if "error" in case:
        if status != "error":
            return False, f"expected error, got {reply!r}", (status, reply)
        if case["error"] not in str(reply):
            return False, f"error missing {case['error']!r}: {reply!r}", (status, reply)
        return True, "", (status, reply)
    if status != "ok":
        return False, f"unexpected error: {reply!r}", (status, reply)
    for key, want in case["expect"].items():
        if reply.get(key) != want:  # type: ignore[union-attr]
            return False, f"{key}: want {want!r}, got {reply.get(key)!r}", (status, reply)  # type: ignore[union-attr]
    return True, "", (status, reply)


def run(*, verbose: bool = False, human_readable: bool = False) -> tuple[int, int]:
    """Run every golden case; print per the flags; return (passed, failed)."""
    passed = failed = 0
    for case in GOLDEN:
        ok, reason, (status, reply) = _check(case)
        passed += ok
        failed += not ok
        if verbose:
            print(
                json.dumps(
                    {"request": case["args"], "reply": {"status": status, "body": reply}}, indent=2
                )
            )
        if human_readable:
            arrow = f"{case['args']['from_expr']} -> {case['args']['to_expr']}"
            body = reply.get("result", reply) if status == "ok" else f"error: {reply}"
            print(
                f"  {'PASS' if ok else 'FAIL'}  {arrow} = {body}"
                + (f"   [{reason}]" if not ok else "")
            )
        elif not ok:
            print(f"FAIL: {case['args']} — {reason}", file=sys.stderr)
    print(f"convert e2e: {passed}/{passed + failed} passed")
    return passed, failed


def test_e2e_convert(request):
    """Pytest entry point — quiet by default; fails if any golden pin regresses.

    Honors ./run-tests.sh's switches: `--human-readable` frames each conversion
    as a readable line, `--verbose`/`-v` prints request/reply JSON (both need
    capture off, which run-tests.sh supplies via -s). --human-readable wins when
    both are given, matching the mcp-abacus conftest.
    """
    human_readable = request.config.getoption("--human-readable")
    verbose = not human_readable and request.config.option.verbose >= 1
    _passed, failed = run(verbose=verbose, human_readable=human_readable)
    assert failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="convert tool end-to-end golden pins")
    parser.add_argument("--verbose", action="store_true", help="print each request/reply as JSON")
    parser.add_argument(
        "--human-readable", action="store_true", help="print each conversion in a readable line"
    )
    ns = parser.parse_args()
    _passed, failed = run(verbose=ns.verbose, human_readable=ns.human_readable)
    sys.exit(1 if failed else 0)
