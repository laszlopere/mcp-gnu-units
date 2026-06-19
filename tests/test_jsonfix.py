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

"""Tests for the tolerant argument-repair fallback (TODO §4.6.5 / §7).

Two layers: pure-function unit tests of `repair_arguments` / `process_incoming`,
and a raw-protocol end-to-end test over a real subprocess that proves a
`tools/call` whose `arguments` arrive as a STRING is repaired and run, or — when
unparseable — answered with an actionable JSON-RPC parse error. The e2e calls
the only registered tool, `info` (no required arguments).
"""

import json
import select
import subprocess
import sys

import pytest
from mcp.shared.message import SessionMessage
from mcp.types import (
    LATEST_PROTOCOL_VERSION,
    PARSE_ERROR,
    JSONRPCMessage,
    JSONRPCRequest,
)

from mcp_gnu_units.jsonfix import process_incoming, repair_arguments

# --- repair_arguments: the pure core -----------------------------------------


def test_passes_through_a_real_dict_unchanged():
    args = {"from": "1 mile", "to": "km"}
    assert repair_arguments(args) is args


def test_parses_a_well_formed_json_string_blob():
    assert repair_arguments('{"from": "1 mile"}') == {"from": "1 mile"}


def test_repairs_single_quotes_and_trailing_comma():
    assert repair_arguments("{'from': '1 mile',}") == {"from": "1 mile"}


def test_repairs_unquoted_bareword_value():
    # The classic offender: "to": km  ->  "km"
    assert repair_arguments('{"to": km}') == {"to": "km"}


def test_unrepairable_garbage_is_returned_unchanged():
    # json-repair coerces junk to "" -- never surface that; hand the original
    # string back so the SDK raises its own informative validation error.
    assert repair_arguments("not json at all") == "not json at all"


def test_a_json_string_that_is_not_an_object_is_left_alone():
    assert repair_arguments('"just a string"') == '"just a string"'
    assert repair_arguments("[1, 2, 3]") == "[1, 2, 3]"


def test_non_string_non_dict_inputs_pass_through():
    assert repair_arguments(None) is None
    assert repair_arguments(42) == 42


# --- process_incoming: the message-level router ------------------------------


def _call_message(arguments) -> SessionMessage:
    req = JSONRPCRequest(
        jsonrpc="2.0",
        id=1,
        method="tools/call",
        params={"name": "convert", "arguments": arguments},
    )
    return SessionMessage(message=JSONRPCMessage(req))


def test_message_with_string_arguments_is_repaired_and_forwarded():
    out = process_incoming(_call_message("{'from': '1 mile',}"))
    assert out.reply is None
    assert out.forward.message.root.params["arguments"] == {"from": "1 mile"}


def test_message_with_dict_arguments_is_forwarded_untouched():
    msg = _call_message({"from": "1 mile"})
    out = process_incoming(msg)
    assert out.reply is None
    assert out.forward is msg


def test_non_tools_call_message_is_forwarded_untouched():
    req = JSONRPCRequest(jsonrpc="2.0", id=1, method="tools/list", params={})
    msg = SessionMessage(message=JSONRPCMessage(req))
    out = process_incoming(msg)
    assert out.reply is None
    assert out.forward is msg


def test_unparseable_string_arguments_yield_a_parse_error_reply():
    out = process_incoming(_call_message("{bad json"))
    assert out.forward is None
    error = out.reply.message.root.error
    assert error.code == PARSE_ERROR
    assert error.message.lower().count("json") >= 1
    assert "object" in error.message  # tells the model to send an object


# --- raw-protocol end-to-end: the honest proof (§4.6.5) ----------------------


class _RawStdioServer:
    """A subprocess speaking newline-delimited JSON-RPC over stdio."""

    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "mcp_gnu_units"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def send(self, obj: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def recv(self, timeout: float = 10.0) -> dict:
        assert self.proc.stdout is not None
        ready, _, _ = select.select([self.proc.stdout], [], [], timeout)
        if not ready:
            raise TimeoutError("no JSON-RPC line within timeout")
        return json.loads(self.proc.stdout.readline())

    def recv_id(self, want_id: int, timeout: float = 10.0) -> dict:
        while True:
            msg = self.recv(timeout)
            if msg.get("id") == want_id:
                return msg

    def close(self) -> None:
        self.proc.terminate()
        self.proc.wait(timeout=5)


@pytest.fixture
def raw_server():
    server = _RawStdioServer()
    server.send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        }
    )
    server.recv_id(1)
    server.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    try:
        yield server
    finally:
        server.close()


def _call(raw_server, call_id, name, arguments):
    raw_server.send(
        {
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    return raw_server.recv_id(call_id)


def test_stringified_arguments_run_end_to_end(raw_server):
    # The arguments double-encoded as a STRING, with single quotes and a trailing
    # comma -- rejected outright without the repair interposer. Repaired to an
    # object and `info` runs (it ignores the extra key).
    msg = _call(raw_server, 2, "info", "{'unused': 'x',}")
    result = msg["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload["status"] == "available"
    assert payload["name"] == "mcp-gnu-units"


def test_unparseable_arguments_get_actionable_parse_error(raw_server):
    # A string that cannot be parsed into an object -> actionable -32700, not the
    # SDK's bare "Invalid request parameters".
    msg = _call(raw_server, 2, "info", "{bad json")
    assert "result" not in msg
    error = msg["error"]
    assert error["code"] == PARSE_ERROR
    assert "JSON object" in error["message"]
