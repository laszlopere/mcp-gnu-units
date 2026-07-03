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

"""Shared pytest configuration.

Registers ``--human-readable`` so ./run-tests.sh can pass it through to pytest
(it adds -s so the output is not captured). The e2e suites read it — and pytest's
own -v — to narrate their conversions; see tests/test_e2e_convert.py.
"""


def pytest_addoption(parser):
    """Register ``--human-readable`` (off by default; pair with -s to see output)."""
    parser.addoption(
        "--human-readable",
        action="store_true",
        default=False,
        help="Frame each conversion as a readable line (run-tests.sh adds -s).",
    )
