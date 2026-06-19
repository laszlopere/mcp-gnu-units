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

"""Pure-function tests for the tolerant argument-repair fallback (TODO §4.6.5).

These cover `repair_arguments` (each offender + the garbage-guard) and the
`process_incoming` message router (repair / forward / parse-error reply). The
raw-stdio end-to-end test that sends a STRING `arguments` blob to a real tool is
DEFERRED to §7: it needs a registered tool to call, which arrives with the
`info` tool in §5.
"""

from mcp.shared.message import SessionMessage
from mcp.types import (
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
