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

"""Unit tests for the argument-validation error formatter (TODO §4.6.5)."""

import pydantic
import pytest

from mcp_gnu_units.errors import format_validation_error

_Model = pydantic.create_model(
    "_Model",
    value=(str, ...),
    digits=(int, ...),
)


def _error(payload) -> pydantic.ValidationError:
    with pytest.raises(pydantic.ValidationError) as info:
        _Model.model_validate(payload)
    return info.value


def test_missing_field_is_named_as_required():
    msg = format_validation_error("convert", _error({"digits": 0}))
    assert "argument 'value' is required but was not provided" in msg
    assert msg.startswith("Invalid arguments for tool 'convert':")


def test_wrong_type_reports_expected_and_received():
    msg = format_validation_error("convert", _error({"value": 123, "digits": 0}))
    assert "argument 'value' expected a string, but received 123 (int)" in msg


def test_integer_field_phrasing():
    msg = format_validation_error("convert", _error({"value": "x", "digits": "abc"}))
    assert "argument 'digits' expected an integer" in msg


def test_multiple_errors_are_joined():
    msg = format_validation_error("convert", _error({}))
    assert "'value'" in msg and "'digits'" in msg
    assert "; " in msg


def test_no_pydantic_url_leaks():
    msg = format_validation_error("convert", _error({}))
    assert "pydantic.dev" not in msg
