"""The evaluator is shared by tool calls that MCPServer runs on worker threads."""

import threading

from mcp_gnu_units.engine.ast import UnitRef
from mcp_gnu_units.engine.evaluator import Evaluator


def test_resolution_in_progress_on_one_thread_is_not_circular_on_another(symbols):
    # Thread A is part-way through reducing 'foot' (its cycle guard holds the
    # name) when thread B asks for 'foot' too. B must reduce it, not report a
    # circular definition.
    ev = Evaluator(symbols)
    ev._resolving.add("foot")
    result: dict = {}

    def other_thread() -> None:
        try:
            result["q"] = ev.reduce_expr(UnitRef("foot"))
        except Exception as exc:  # noqa: BLE001 - the test reports what was raised
            result["err"] = exc

    t = threading.Thread(target=other_thread)
    t.start()
    t.join()
    assert "err" not in result, result.get("err")
    assert float(result["q"].coefficient.as_float()) == 0.3048
