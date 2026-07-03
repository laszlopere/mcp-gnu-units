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

"""§17.2 — end-to-end golden pins for the `convert_to_si` tool, exercised through
the FastMCP layer (`mcp.call_tool`), same path a real client drives.

Two ways to run it:
  * as part of the suite — `uv run pytest` collects `test_e2e_convert_to_si` below;
  * as a standalone script — `python tests/test_e2e_convert_to_si.py`:
        (no options)       print only the pass/fail statistics
        --verbose          also print each request/reply as JSON
        --human-readable   also print each reduction in a readable line
"""

import argparse
import asyncio
import json
import sys

from mcp.server.fastmcp.exceptions import ToolError

from mcp_gnu_units.server import mcp

# Golden reductions with pinned answers. `expect` cases must succeed and every
# listed field must match; `error` cases must raise a ToolError containing the
# substring. Values were pinned against the tool's real output, not hand-computed.
# ⚠️ 'h' is Planck's constant in GNU units, so energy is 'kW*hour', not 'kW*h'.
GOLDEN: list[dict] = [
    # -- derived units collapse to base dimensions ------------------------
    {
        "args": {"expr": "kW*hour"},  # 3.6 MJ of energy in base units
        "expect": {
            "result": "3600000 kg m^2 / s^2",
            "value": 3600000.0,
            "dimension": "kg m^2 / s^2",
            "exact": True,
        },
    },
    {
        "args": {"expr": "newton"},
        "expect": {
            "result": "1 kg m / s^2",
            "value": 1.0,
            "dimension": "kg m / s^2",
            "exact": True,
        },
    },
    {
        "args": {"expr": "100 W"},
        "expect": {
            "result": "100 kg m^2 / s^3",
            "value": 100.0,
            "dimension": "kg m^2 / s^3",
            "exact": True,
        },
    },
    {
        "args": {"expr": "1 atm"},
        "expect": {
            "result": "101325 kg / m s^2",
            "value": 101325.0,
            "dimension": "kg / m s^2",
            "exact": True,
        },
    },
    # -- prefixed / imperial units reduce to coherent SI ------------------
    {
        "args": {"expr": "mile"},
        "expect": {"result": "1609.344 m", "value": 1609.344, "dimension": "m", "exact": True},
    },
    {
        "args": {"expr": "55 mile/hour"},
        "expect": {"result": "24.5872 m / s", "dimension": "m / s", "exact": True},
    },
    # exact ratio whose 12-significant-figure rendering is a rounded decimal:
    # `exact` reports the internal rational, NOT the truncated display string.
    {
        "args": {"expr": "acre ft"},
        "expect": {"result": "1233.48183755 m^3", "dimension": "m^3", "exact": True},
    },
    # -- data units (binary prefixes) -> bits -----------------------------
    {
        "args": {"expr": "1 GiB"},
        "expect": {
            "result": "8589934592 bit",
            "value": 8589934592.0,
            "dimension": "bit",
            "exact": True,
        },
    },
    # -- amount of substance ----------------------------------------------
    {
        "args": {"expr": "1 mole"},
        "expect": {"result": "1 mol", "value": 1.0, "dimension": "mol", "exact": True},
    },
    # -- dimensionless reduces to the bare coefficient "1" ----------------
    {
        "args": {"expr": "radian"},
        "expect": {"result": "1", "value": 1.0, "dimension": "1", "exact": True},
    },
    # -- inexact result (irrational coefficient) --------------------------
    {
        "args": {"expr": "sqrt(2) m"},
        "expect": {"result": "1.41421356237 m", "dimension": "m", "exact": False},
    },
    # -- error paths (each must fail cleanly, not crash) ------------------
    # a nonlinear unit has no linear base form
    {"args": {"expr": "tempF"}, "error": "'tempF' is not a defined unit"},
    {"args": {"expr": "bogusunit"}, "error": "'bogusunit' is not a defined unit"},
    {"args": {"expr": "kg//"}, "error": "unexpected SLASH"},
]


def _call(args: dict) -> tuple[str, object]:
    """Invoke `convert_to_si` through the app; return ('ok', payload) or ('error', message)."""

    async def go():
        return await mcp.call_tool("convert_to_si", args)

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
            arrow = f"{case['args']['expr']} -> SI"
            body = reply.get("result", reply) if status == "ok" else f"error: {reply}"
            print(
                f"  {'PASS' if ok else 'FAIL'}  {arrow} = {body}"
                + (f"   [{reason}]" if not ok else "")
            )
        elif not ok:
            print(f"FAIL: {case['args']} — {reason}", file=sys.stderr)
    print(f"convert_to_si e2e: {passed}/{passed + failed} passed")
    return passed, failed


def test_e2e_convert_to_si(request):
    """Pytest entry point — quiet by default; fails if any golden pin regresses.

    Honors ./run-tests.sh's switches: `--human-readable` frames each reduction as
    a readable line, `--verbose`/`-v` prints request/reply JSON (both need capture
    off, which run-tests.sh supplies via -s). --human-readable wins when both are
    given, matching test_e2e_convert.py.
    """
    human_readable = request.config.getoption("--human-readable")
    verbose = not human_readable and request.config.option.verbose >= 1
    _passed, failed = run(verbose=verbose, human_readable=human_readable)
    assert failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="convert_to_si tool end-to-end golden pins")
    parser.add_argument("--verbose", action="store_true", help="print each request/reply as JSON")
    parser.add_argument(
        "--human-readable", action="store_true", help="print each reduction in a readable line"
    )
    ns = parser.parse_args()
    _passed, failed = run(verbose=ns.verbose, human_readable=ns.human_readable)
    sys.exit(1 if failed else 0)
