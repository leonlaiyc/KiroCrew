"""Scratch probe: drop every skipif that fires on this host, record its reason."""
import json
import os

_REASONS = {}


def _truthy_skipifs(node):
    out = []
    for m in node.own_markers:
        if m.name != "skipif":
            continue
        cond = m.args[0] if m.args else m.kwargs.get("condition")
        if isinstance(cond, bool) and cond:
            out.append(m)
    return out


def pytest_collection_modifyitems(session, config, items):
    nodes = {}
    for item in items:
        reasons = []
        for node in item.listchain():
            for m in _truthy_skipifs(node):
                reasons.append(str(m.kwargs.get("reason", "")))
            nodes[id(node)] = node
        if reasons:
            _REASONS[item.nodeid] = reasons
    for node in nodes.values():
        node.own_markers[:] = [m for m in node.own_markers if m not in _truthy_skipifs(node)]
    items[:] = [i for i in items if i.nodeid in _REASONS]


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        path = os.environ.get("UNSKIP_OUT", "unskip.jsonl")
        with open(path + "." + os.environ.get("PYTEST_XDIST_WORKER", "m"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": report.nodeid, "when": report.when, "outcome": report.outcome,
                                 "reasons": _REASONS.get(report.nodeid, [])}) + "\n")
