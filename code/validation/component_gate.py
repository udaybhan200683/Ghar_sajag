#!/usr/bin/env python3
"""GS-116 registered component and full-product software gates; no board access."""
from __future__ import annotations
import argparse, hashlib, json, os, re, signal, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"validation/suites.json"
COMPONENTS={"node","hub","contract","backend","pwa","tooling"}
SPECIAL_SUITES={"fast","release","board-e2e","p0-e2e"}
CLASSIC_SKIP="classic ESP32 NVS reserve model is historical under GS-D030; S3 commercial capacity and reserve qualification remain open"

def load_registry(path=REGISTRY, root=ROOT):
    data=json.loads(path.read_text())
    if data.get("schema_version")!=1 or not data.get("stages"):
        raise ValueError("unsupported registry or zero registered stages")
    ids=set()
    for s in data["stages"]:
        if s["id"] in ids or not re.fullmatch(r"[a-z0-9-]+",s["id"]):
            raise ValueError("duplicate/invalid stage id")
        ids.add(s["id"])
        if not s.get("components") or set(s["components"])-COMPONENTS:
            raise ValueError("missing/invalid component ownership")
        if not s.get("command") or not all(isinstance(x,str) for x in s["command"]):
            raise ValueError("missing command")
        if not s.get("success") or s.get("timeout",0)<=0:
            raise ValueError("missing success evidence or timeout")
        if "pwa" in s and (s["pwa"] is not True or "pwa" not in s["components"]):
            raise ValueError("PWA-only selector requires an explicit PWA-owned stage: "+s["id"])
        for f in s.get("inputs",[]):
            if not (root/f).is_file(): raise ValueError("missing dependency: "+f)
        if s.get("require_complete_product") and not (s.get("fast") and s.get("release", True)):
            raise ValueError("complete product stage must belong to developer and release gates: "+s["id"])
    for s in data["stages"]:
        prerequisites=s.get("prerequisites",[])
        if len(prerequisites)!=len(set(prerequisites)) or s["id"] in prerequisites or set(prerequisites)-ids:
            raise ValueError("missing, duplicate, or self prerequisite for stage: "+s["id"])
    for name, suite in data.get("opt_in_physical_suites", {}).items():
        if name not in {"validation-board-hil", "validation-motion-hil"}:
            raise ValueError("unknown physical suite: "+name)
        if suite.get("automatic") is not False or suite.get("included_in_software_gates") is not False:
            raise ValueError("physical suites must remain explicitly opt-in: "+name)
        if not suite.get("requires_operator_confirmation") or not suite.get("command"):
            raise ValueError("physical suite missing command/confirmation boundary: "+name)
    if not COMPONENTS.issubset({c for s in data["stages"] for c in s["components"]}):
        raise ValueError("required component suite missing")
    owned={f for s in data["stages"] for f in s.get("inputs",[])}
    exceptions=data.get("separate_harnesses",{})
    for p in (root/"tests/cpp").glob("*.cpp"):
        if re.search(r"int\s+main\s*\(",p.read_text()):
            name=str(p.relative_to(root))
            if name not in owned and not exceptions.get(name):
                raise ValueError("unregistered executable test: "+name)
    return data

def select(data,suite):
    if suite not in COMPONENTS|SPECIAL_SUITES: raise ValueError("unknown suite")
    selected={s["id"] for s in data["stages"] if
        (suite=="board-e2e" and s["id"]=="board-stack-e2e") or
        (suite=="p0-e2e" and s["id"]=="p0-full-product-e2e") or
        (suite=="release" and (s.get("fast",True) or s.get("release",False))) or
        (suite=="fast" and s.get("fast",True)) or
        (suite in s["components"] and s.get("fast",True)) or
        (suite=="pwa" and s.get("pwa",False))}
    if not selected: raise ValueError("zero selected stages")
    by_id={s["id"]:s for s in data["stages"]}
    pending=list(selected)
    while pending:
        current=pending.pop()
        for prerequisite in by_id[current].get("prerequisites",[]):
            if prerequisite not in selected:
                selected.add(prerequisite);pending.append(prerequisite)
    selected=[s for s in data["stages"] if s["id"] in selected]
    if not selected: raise ValueError("zero selected stages")
    return selected

def source_fingerprint(root=ROOT, extra=()):
    names=subprocess.check_output(["git","ls-files"],cwd=root,text=True).splitlines()
    files={n for n in names if not n.endswith(".md")}
    # Include every registered input, including newly added untracked tests,
    # independent of the selected component. Partition CSVs are build inputs.
    registry=root/"validation/suites.json"
    if registry.is_file():
        files.update(f for s in json.loads(registry.read_text())["stages"] for f in s.get("inputs",[]))
    files.update(extra)
    files.update(("validation/component_gate.py","validation/suites.json",
        "scripts/host_build_profile.py","scripts/build_validation_targets.py",
        "tests/python/test_component_gate.py","../../Makefile"))
    h=hashlib.sha256()
    for n in sorted(files):
        p=root/n
        if p.is_file(): h.update(n.encode()+b"\0"+p.read_bytes()+b"\0")
    return h.hexdigest()

def run_process(command,cwd,env,timeout):
    started=time.monotonic()
    try:
        proc=subprocess.Popen(command,cwd=cwd,env=env,text=True,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
    except OSError as error:
        return {"exit_code":127,"output":"DEPENDENCY_ERROR: "+str(error),"seconds":time.monotonic()-started}
    try:
        output,_=proc.communicate(timeout=timeout);rc=proc.returncode
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid,signal.SIGKILL)
        output,_=proc.communicate();rc=124
        output+="\nTIMEOUT: owned process group terminated\n"
    except BaseException:
        # Cancellation must not orphan compilers, HTTP labs or test children.
        try: os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        proc.communicate()
        raise
    return {"exit_code":rc,"output":output,"seconds":round(time.monotonic()-started,3)}

def stage_environment(stage,env):
    """Keep browser endpoint overrides scoped to the registered browser stage."""
    child=env.copy()
    if stage["id"]!="browser":
        child.pop("PLAYWRIGHT_PORT",None)
        child.pop("PWA_BASE_URL",None)
    return child

def adjudicate(stage,result):
    out=result["output"]
    if result["exit_code"]: return "FAIL"
    if any(re.search(pattern,out,re.M) for pattern in stage.get("failure_patterns",[])):
        return "FAIL"
    if re.search(r"^\s*[1-9]\d* (?:skipped|did not run|interrupted)\b|^# (?:skipped|todo) [1-9]\d*\b",out,re.M):
        return "FAIL"
    if re.search(r"Ran 0 tests|(?:tests|checks)=0\b|^\s*0 passed\b",out,re.M): return "FAIL"
    matches=list(re.finditer(stage["success"],out,re.M))
    if not matches: return "FAIL"
    if stage.get("require_complete_product") and re.search(r"product_status=(?:PARTIAL|BLOCKED|NOT_RUN)",out): return "FAIL"
    if any(not re.search(pattern,out,re.M) for pattern in stage.get("required_success",[])):
        return "FAIL"
    for m in matches:
        if m.lastindex and m.group(1).isdigit() and int(m.group(1))==0: return "FAIL"
    skipped=re.findall(r"\.\.\. skipped '([^']+)'",out)
    if any(reason not in stage.get("allowed_skips",[]) for reason in skipped): return "FAIL"
    summary=re.search(r"OK \(skipped=(\d+)\)",out)
    if summary and int(summary.group(1))!=len(skipped): return "FAIL"
    for line in out.splitlines():
        if re.search(r"\b(?:SKIP|SKIPPED|MANUAL_REQUIRED|ALREADY_PASSED)\b",line):
            if not any(re.search(p,line) for p in stage.get("allowed_skip_lines",[])): return "FAIL"
    return "PASS"

def software_report_status(rows,physical="NOT_RUN"):
    return {"software_status":"PASS" if rows and all(r["status"]=="PASS" for r in rows) else "FAIL",
            "physical_status":physical,"physically_qualified":False,"release_approved":False}

def artifact_records(output,root=ROOT):
    names=set(re.findall(r'(?:^|\s)-o\s+([^\s]+)',output))
    for report_name in re.findall(r'^TARGET REPORT (.+)$',output,re.M):
        report_path=Path(report_name)
        if report_path.is_file():
            names.add(str(report_path))
            target_report=json.loads(report_path.read_text())
            for image in target_report.get("images",{}).values():
                names.update(str(p) for p in Path(image["build"]).glob("*.bin"))
    records={}
    for name in names:
        p=root/name
        if p.is_file(): records[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    return records

def verify_receipt(stage,row,report,stamp,profile,root=ROOT):
    if report.get("source_fingerprint")!=stamp or not report.get("source_unchanged") or report.get("build_profile")!=profile:
        raise ValueError("STALE_ARTIFACT: receipt source/profile mismatch")
    if row.get("command")!=stage["command"] or row.get("status")!="PASS":
        raise ValueError("invalid mandatory receipt")
    log=root/row["log"]
    if not log.is_file() or hashlib.sha256(log.read_bytes()).hexdigest()!=row.get("log_sha256"):
        raise ValueError("STALE_ARTIFACT: missing/changed executed-stage log")
    for name,digest in row.get("artifacts",{}).items():
        artifact=root/name
        if not artifact.is_file() or hashlib.sha256(artifact.read_bytes()).hexdigest()!=digest:
            raise ValueError("STALE_ARTIFACT: missing/changed binary "+name)
    result={"exit_code":row["exit_code"],"output":log.read_text(),"seconds":0}
    if adjudicate(stage,result)!="PASS": raise ValueError("invalid mandatory execution/count/skip receipt")
    return result

def build_profile(env):
    profile={k:env.get(k,"") for k in ("CXX","HOST_CXX","HOST_TOOLCHAIN_GUARD",
        "CXXFLAGS","TRACE_FLAGS","INCLUDES","PRODUCT","GS_IDF_EXPORT")}
    profile["host_compiler"]=subprocess.check_output(
        [sys.executable,"scripts/host_build_profile.py","--compiler-only",env.get("CXX","g++")],cwd=ROOT,text=True).strip()
    import importlib.util
    spec=importlib.util.spec_from_file_location("portable_psa_dependency",ROOT/"scripts/build_portable_psa_reset.py")
    dependency=importlib.util.module_from_spec(spec);spec.loader.exec_module(dependency)
    profile["portable_crypto_sources"]=dependency.dependency_fingerprint(env)
    profile["python"]=sys.version
    return profile

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--suite",required=True,choices=sorted(COMPONENTS|SPECIAL_SUITES))
    p.add_argument("--list",action="store_true")
    p.add_argument("--reuse-report",type=Path,action="append",default=[],
        help="explicit same-source/profile executed prerequisites, verified logs and binaries")
    args=p.parse_args(argv)
    try:
        data=load_registry();stages=select(data,args.suite)
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as error:
        print("REGISTRATION FAIL:",error);return 2
    if args.list:
        for s in stages: print(s["id"]," ".join(s["command"]))
        return 0
    extra=["validation/component_gate.py","validation/suites.json",
           "tests/python/test_component_gate.py","scripts/build_validation_targets.py",
           *[f for s in stages for f in s.get("inputs",[])]]
    stamp=source_fingerprint(extra=extra)
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    campaign=ROOT/"evidence/validation_framework"/(args.suite+"-"+str(time.time_ns()))
    campaign.mkdir(parents=True)
    rows=[];started=time.monotonic()
    env={**os.environ,"PYTHONPATH":str(ROOT/"backend")+os.pathsep+str(ROOT),"PYTHONUNBUFFERED":"1"}
    profile=build_profile(env)
    receipts={}
    try:
        for path in args.reuse_report:
            previous=json.loads(path.read_text())
            for row in previous["stages"]:
                if row["status"]=="PASS": receipts[row["id"]]=(row,previous,str(path))
    except (OSError,ValueError,KeyError) as error:
        print("RECEIPT FAIL:",error);return 2
    forbidden=[k for k in ("GS_RELEASE_GATE_SKIP_MASTER","GS_RELEASE_GATE_SKIP_FOTA_HOST",
                          "RELEASE_GATE_FINAL_SKIP_PERFORMANCE") if env.get(k)=="1"]
    if forbidden:
        print("Unverified mandatory-stage bypass rejected:",",".join(forbidden));return 2
    for stage in stages:
        print("START",stage["id"],"timeout="+str(stage["timeout"]),flush=True)
        reused=None
        if stage["id"] in receipts:
            row,previous,reused=receipts[stage["id"]]
            try: result=verify_receipt(stage,row,previous,stamp,profile)
            except (ValueError,OSError,KeyError) as error:
                result={"exit_code":2,"output":str(error),"seconds":0}
        else: result=run_process(stage["command"],ROOT,stage_environment(stage,env),stage["timeout"])
        result["status"]=adjudicate(stage,result)
        log=campaign/(stage["id"]+".log");log.write_text(result.pop("output"))
        text=log.read_text();count_matches=list(re.finditer(stage["success"],text,re.M))
        count=sum(int(m.group(1)) if m.lastindex and m.group(1).isdigit() else 1 for m in count_matches)
        result.update(id=stage["id"],command=stage["command"],count=count,
            count_kind=stage.get("count_kind","assertion_groups"),log=str(log.relative_to(ROOT)),
            log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
            artifacts=artifact_records(text),reused_from=reused,components=stage["components"])
        if reused and result["status"]=="PASS": result["artifacts"]=row.get("artifacts",{})
        rows.append(result)
        print(result["status"],stage["id"],"exit="+str(result["exit_code"]),
              "count="+str(count),str(result["seconds"])+"s",flush=True)
        if result["status"]!="PASS": print(text[-3000:],flush=True)
    unchanged=source_fingerprint(extra=extra)==stamp
    report={**software_report_status(rows),"suite":args.suite,"source_head":head,
        "source_fingerprint":stamp,"source_unchanged":unchanged,
        "build_profile":profile,
        "tracked_dirty":bool(subprocess.check_output(["git","status","--porcelain","--untracked-files=no"],cwd=ROOT,text=True).strip()),
        "seconds":round(time.monotonic()-started,3),"stages":rows}
    if not unchanged: report["software_status"]="FAIL";report["reason"]="STALE_ARTIFACT: source changed during campaign"
    (campaign/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    print("SOFTWARE",report["software_status"],"PHYSICAL NOT_RUN",campaign/"report.json",flush=True)
    return 0 if report["software_status"]=="PASS" else 1

if __name__=="__main__": raise SystemExit(main())
