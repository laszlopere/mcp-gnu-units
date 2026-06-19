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

"""Directive state machine driving conditional definition blocks (TODO §2.4.8).

GNU units gates blocks of definitions on variables (``!var``/``!varnot``), the
output encoding (``!utf8``), and the locale (``!locale``). A definition is added
to the symbol table only when EVERY enclosing block is active — the AND of the
context stack. The default variable environment (``UNITS_SYSTEM=default``,
``UNITS_ENGLISH=US``, ``locale=en_US``, ``utf8=True``) mirrors the binary, so we
load the same units a plain ``units`` invocation would.
"""

from __future__ import annotations

from dataclasses import dataclass

from .symbols import LoadConfig, SymbolTable


@dataclass
class _Frame:
    kind: str  # 'var' | 'varnot' | 'utf8' | 'locale'
    active: bool


class DirectiveProcessor:
    """Tracks the conditional-block stack and the variable environment."""

    def __init__(self, config: LoadConfig, symbols: SymbolTable) -> None:
        self._config = config
        self._symbols = symbols
        self.env: dict[str, str] = {
            "UNITS_SYSTEM": config.units_system,
            "UNITS_ENGLISH": config.units_english,
        }
        self.env.update(config.extra)
        self._stack: list[_Frame] = []
        self.prompt: str | None = None

    @property
    def active(self) -> bool:
        return all(frame.active for frame in self._stack)

    def handle(self, body: str) -> None:
        """Process a directive (``body`` is the text after the leading ``!``)."""
        head, _, rest = body.partition(" ")
        rest = rest.strip()
        # Re-split because there may be runs of whitespace after the name.
        name = head.strip()
        args = body[len(head) :].strip()

        if name == "var":
            self._push_var(args, negate=False)
        elif name == "varnot":
            self._push_var(args, negate=True)
        elif name == "endvar":
            self._pop(("var", "varnot"))
        elif name == "utf8":
            self._stack.append(_Frame("utf8", self._config.utf8))
        elif name == "endutf8":
            self._pop(("utf8",))
        elif name == "locale":
            self._stack.append(_Frame("locale", self._config.locale == args.strip()))
        elif name == "endlocale":
            self._pop(("locale",))
        elif name == "set":
            if self.active:
                self._set(args)
        elif name == "prompt":
            if self.active:
                self.prompt = args
        elif name == "unitlist":
            if self.active:
                self._unitlist(args)
        # !message, !include, and any unknown directive are inert for loading.
        # (!include targets non-bundled data files that the binary also skips.)

    # -- handlers --------------------------------------------------------

    def _push_var(self, args: str, *, negate: bool) -> None:
        tokens = args.split()
        if not tokens:
            self._stack.append(_Frame("varnot" if negate else "var", False))
            return
        var, values = tokens[0], tokens[1:]
        present = self.env.get(var) in values
        active = (not present) if negate else present
        self._stack.append(_Frame("varnot" if negate else "var", active))

    def _pop(self, kinds: tuple[str, ...]) -> None:
        if self._stack and self._stack[-1].kind in kinds:
            self._stack.pop()

    def _set(self, args: str) -> None:
        tokens = args.split(None, 1)
        if not tokens:
            return
        var = tokens[0]
        value = tokens[1].strip() if len(tokens) > 1 else ""
        self.env.setdefault(var, value)

    def _unitlist(self, args: str) -> None:
        name, _, members_str = args.partition(" ")
        members = [m.strip() for m in members_str.split(";") if m.strip()]
        if name and members:
            self._symbols.add_unitlist(name.strip(), members)
