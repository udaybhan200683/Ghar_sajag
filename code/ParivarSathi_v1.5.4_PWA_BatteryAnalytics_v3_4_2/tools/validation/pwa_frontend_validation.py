#!/usr/bin/env python3
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from typing import Any
try:
    from functional_scenarios import DEFAULT_CATALOG, _execute_step, load_catalog
except ModuleNotFoundError:
    from .functional_scenarios import DEFAULT_CATALOG, _execute_step, load_catalog

def catalog_for_frontend(path: Path = DEFAULT_CATALOG) -> dict[str, Any]:
    catalog=load_catalog(path)
    return {"schema":1,"release":catalog.get("release","unknown"),"count":len(catalog["scenarios"]),"scenarios":[{"id":s["id"],"title":s["title"],"category":s["category"],"requirements":s.get("requirements",[]),"assertions":deepcopy(s.get("assertions",[]))} for s in catalog["scenarios"]]}

def execute_for_frontend(lab, scenario_id: str, path: Path = DEFAULT_CATALOG) -> dict[str, Any]:
    catalog=load_catalog(path)
    scenario=next((s for s in catalog["scenarios"] if s["id"]==scenario_id),None)
    if scenario is None: raise ValueError("unknown validation scenario")
    variables={}; step_results=[]; lab.reset(test_fixture=True)
    for index,step in enumerate(scenario.get("steps",[]),1):
        ok,detail=_execute_step(lab,deepcopy(step),variables)
        step_results.append({"index":index,"passed":bool(ok),"detail":detail})
        if not ok: break
    return {"schema":1,"release":catalog.get("release","unknown"),"scenario":{"id":scenario["id"],"title":scenario["title"],"category":scenario["category"],"requirements":scenario.get("requirements",[]),"assertions":deepcopy(scenario.get("assertions",[]))},"steps_passed":all(x["passed"] for x in step_results),"step_results":step_results,"state":lab.snapshot()}
