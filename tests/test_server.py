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

"""§7.3 — prove the `info` tool is wired into the FastMCP app, not merely
importable. Introspect and invoke it through the MCP layer (end-to-end)."""

import asyncio
import json

from mcp_gnu_units.server import mcp


def _call_via_app(name: str, arguments: dict) -> dict:
    """Invoke a tool through the app and return its parsed JSON payload."""

    async def go():
        return await mcp.call_tool(name, arguments)

    result = asyncio.run(go())
    # call_tool returns a list of content blocks; the payload is JSON text.
    contents = result[0] if isinstance(result, tuple) else result
    return json.loads(contents[0].text)


def _call_info_via_app() -> dict:
    """Invoke `info` through the app and return its parsed JSON payload."""
    return _call_via_app("info", {})


def test_info_and_find_units_are_registered():
    # §7.3.1 — info plus the first domain tool (find_units, §14.1) are exposed.
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"info", "find_units"} <= names


def test_tool_has_description_and_input_schema():
    # §7.3.2 — non-empty description (docstring) + generated input schema.
    tool = next(t for t in asyncio.run(mcp.list_tools()) if t.name == "info")
    assert tool.description and tool.description.strip()
    assert isinstance(tool.inputSchema, dict)
    assert tool.inputSchema.get("type") == "object"


def test_invoke_through_app_matches_payload():
    # §7.3.3 — invoke through the MCP layer; payload matches §7.2.
    from importlib.metadata import version

    payload = _call_info_via_app()
    assert payload["status"] == "available"
    assert payload["name"] == "mcp-gnu-units"
    assert payload["version"] == version("mcp-gnu-units")
    assert payload["python"]
    assert payload["mcp_sdk"]
    assert payload["toolsets"] == []


def test_info_survives_missing_sdk_metadata(monkeypatch):
    # version("mcp") can raise PackageNotFoundError; info must not crash.
    from importlib.metadata import PackageNotFoundError

    from mcp_gnu_units import server

    def boom(_name):
        raise PackageNotFoundError

    monkeypatch.setattr(server, "version", boom)
    payload = _call_info_via_app()
    assert payload["status"] == "available"
    assert payload["mcp_sdk"] == "unknown"


def test_find_units_invoke_through_app():
    # §14.1 — basic substring search wired through the MCP layer end-to-end.
    payload = _call_via_app("find_units", {"query": "meter"})
    assert payload["query"] == "meter"
    assert payload["count"] == len(payload["results"])
    assert payload["count"] > 0
    names = {hit["name"] for hit in payload["results"]}
    assert "meter" in names
    assert all("name" in hit and "definition" in hit for hit in payload["results"])


def test_find_units_limit_is_honored():
    # §14.1 — the `limit` cap bounds the result count.
    payload = _call_via_app("find_units", {"query": "meter", "limit": 3})
    assert payload["count"] == 3


def test_find_units_no_match_returns_empty():
    # §14.1 — a query that matches nothing returns cleanly, not an error.
    payload = _call_via_app("find_units", {"query": "zzzznotaunit"})
    assert payload["count"] == 0
    assert payload["results"] == []
