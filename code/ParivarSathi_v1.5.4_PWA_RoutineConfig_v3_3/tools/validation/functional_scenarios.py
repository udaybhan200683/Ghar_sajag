#!/usr/bin/env python3
"""Declarative functional-scenario runner for the Ghar Sajag host lab.

The catalog is intentionally data-driven so new product behaviour is added as a scenario
rather than as an ad-hoc lambda hidden in local_lab.py.  It operates only through the Lab
public action/snapshot surface, which means scenarios exercise the same C++ -> Python ->
read-model path used by the browser simulator.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "tests" / "functional" / "scenario_catalog.json"


def _path(value: Any, dotted: str) -> Any:
    cur = value
    if not dotted:
        return cur
    for token in dotted.split("."):
        if isinstance(cur, list):
            cur = cur[int(token)]
        elif isinstance(cur, dict):
            if token not in cur:
                raise KeyError(dotted)
            cur = cur[token]
        else:
            raise KeyError(dotted)
    return cur


def _matches(item: Any, where: dict[str, Any]) -> bool:
    for key, expected in where.items():
        try:
            actual = _path(item, key)
        except (KeyError, IndexError, ValueError, TypeError):
            return False
        if actual != expected:
            return False
    return True


def _assert_one(state: dict[str, Any], assertion: dict[str, Any]) -> tuple[bool, str]:
    if "path" in assertion:
        try:
            actual = _path(state, assertion["path"])
        except (KeyError, IndexError, ValueError, TypeError):
            return False, f"path missing: {assertion['path']}"
        for op in ("eq", "ne", "ge", "gt", "le", "lt"):
            if op in assertion:
                expected = assertion[op]
                ok = {
                    "eq": actual == expected,
                    "ne": actual != expected,
                    "ge": actual >= expected,
                    "gt": actual > expected,
                    "le": actual <= expected,
                    "lt": actual < expected,
                }[op]
                return ok, f"{assertion['path']}={actual!r} {op} {expected!r}"
        if assertion.get("truthy") is True:
            return bool(actual), f"{assertion['path']} expected truthy, got {actual!r}"
        if assertion.get("falsy") is True:
            return not bool(actual), f"{assertion['path']} expected falsy, got {actual!r}"
        raise ValueError(f"unsupported path assertion: {assertion}")

    if "select" in assertion:
        try:
            items = _path(state, assertion["select"])
        except (KeyError, IndexError, ValueError, TypeError):
            return False, f"collection missing: {assertion['select']}"
        if not isinstance(items, list):
            return False, f"{assertion['select']} is not a list"
        matches = [item for item in items if _matches(item, assertion.get("where", {}))]
        if "count" in assertion:
            ok = len(matches) == assertion["count"]
            return ok, f"{assertion['select']} matches={len(matches)} expected={assertion['count']} where={assertion.get('where', {})}"
        if "min_count" in assertion:
            ok = len(matches) >= assertion["min_count"]
            return ok, f"{assertion['select']} matches={len(matches)} expected>={assertion['min_count']} where={assertion.get('where', {})}"
        raise ValueError(f"unsupported select assertion: {assertion}")

    if "order" in assertion:
        spec = assertion["order"]
        try:
            items = _path(state, spec["path"])
            actual = [_path(item, spec.get("field", "kind")) for item in items[: len(spec["prefix"])]]
        except (KeyError, IndexError, ValueError, TypeError):
            return False, f"cannot evaluate order: {spec}"
        expected = spec["prefix"]
        return actual == expected, f"order actual={actual!r} expected={expected!r}"

    raise ValueError(f"unsupported assertion: {assertion}")


def _replace_vars(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        return variables[value[1:]]
    if isinstance(value, dict):
        return {k: _replace_vars(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace_vars(v, variables) for v in value]
    return value


def _execute_step(lab, step: dict[str, Any], variables: dict[str, Any]) -> tuple[bool, str]:
    if step.get("capture") == "first_incident":
        snapshot = lab.snapshot()
        if not snapshot["incidents"]:
            return False, "cannot capture first incident: none exists"
        variables[step.get("as", "incident_id")] = snapshot["incidents"][0]["incident_id"]
        return True, "captured first incident"

    expect_error = step.get("expect_error")
    if step.get("action") == "settings_patch":
        snapshot = lab.snapshot()
        settings = {k: v for k, v in snapshot["settings"].items() if k != "config_version"}
        settings.update(deepcopy(step.get("values", {})))
        body = {"action": "settings", "settings": settings}
    else:
        body = _replace_vars(deepcopy(step), variables)
        body.pop("expect_error", None)
    try:
        lab.action(body)
    except Exception as exc:  # expected negative-path errors are part of the catalog
        if expect_error is None:
            return False, f"unexpected {type(exc).__name__}: {exc}"
        text = str(exc)
        return (expect_error in text), f"expected error containing {expect_error!r}; got {text!r}"
    if expect_error is not None:
        return False, f"expected error containing {expect_error!r}, but action succeeded"
    return True, "ok"


def load_catalog(path: Path = DEFAULT_CATALOG) -> dict[str, Any]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if catalog.get("schema") != 1 or not isinstance(catalog.get("scenarios"), list):
        raise ValueError("invalid functional scenario catalog")
    ids = [item.get("id") for item in catalog["scenarios"]]
    if None in ids or len(ids) != len(set(ids)):
        raise ValueError("scenario ids must be non-empty and unique")
    return catalog


def run_catalog(lab, path: Path = DEFAULT_CATALOG, categories: set[str] | None = None) -> dict[str, Any]:
    catalog = load_catalog(path)
    results = []
    for scenario in catalog["scenarios"]:
        if categories and scenario.get("category") not in categories:
            continue
        variables: dict[str, Any] = {}
        failures: list[str] = []
        try:
            lab.reset()
            for index, step in enumerate(scenario.get("steps", []), 1):
                ok, detail = _execute_step(lab, step, variables)
                if not ok:
                    failures.append(f"step {index}: {detail}")
                    break
            state = lab.snapshot()
            if not failures:
                for index, assertion in enumerate(scenario.get("assertions", []), 1):
                    ok, detail = _assert_one(state, assertion)
                    if not ok:
                        failures.append(f"assertion {index}: {detail}")
            results.append({
                "id": scenario["id"],
                "title": scenario["title"],
                "category": scenario["category"],
                "requirements": scenario.get("requirements", []),
                "passed": not failures,
                "failures": failures,
            })
        except Exception as exc:
            results.append({
                "id": scenario["id"], "title": scenario["title"], "category": scenario["category"],
                "requirements": scenario.get("requirements", []), "passed": False,
                "failures": [f"runner exception {type(exc).__name__}: {exc}"],
            })
    passed = sum(1 for item in results if item["passed"])
    return {
        "schema": 1,
        "release": catalog.get("release", "unknown"),
        "status": "PASS" if passed == len(results) else "FAIL",
        "passed": passed,
        "total": len(results),
        "cases": results,
    }
