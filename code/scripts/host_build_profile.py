#!/usr/bin/env python3
"""Separate host object caches by compiler identity and every compile flag."""
import hashlib, json, shutil, subprocess, sys
from pathlib import Path

def source_signature(root,names=None):
    if names is None:
        names=subprocess.check_output(["git","ls-files","--cached","--others","--exclude-standard","--",
            "firmware","shared","host","config","scripts/generate_node_health_config.py",
            "backend/ghar_sajag/node_health_policy.py"],cwd=root,text=True).splitlines()
        names.append("build/gs40_generated/gs/node_health_config.hpp")
    h=hashlib.sha256()
    for name in sorted(set(names)):
        p=root/name
        if "managed_components" in p.parts or p.suffix not in {".cpp",".c",".h",".hpp",".json",".py"}:
            continue
        if p.is_file(): h.update(name.encode()+b"\0"+p.read_bytes()+b"\0")
    return h.hexdigest()

def fingerprint(args,root=None):
    compiler=shutil.which(args[0].split()[0]) or args[0]
    try: version=subprocess.check_output([compiler,"--version"],text=True,stderr=subprocess.STDOUT).splitlines()[0]
    except (OSError,subprocess.SubprocessError): version="UNAVAILABLE"
    source=source_signature(root) if root else ""
    return hashlib.sha256(json.dumps([compiler,version,source,*args],separators=(",",":")).encode()).hexdigest()[:16]
if __name__=="__main__":
    args=sys.argv[1:]
    compiler_only=args and args[0]=="--compiler-only"
    if compiler_only: args=args[1:]
    print(fingerprint(args,None if compiler_only else Path(__file__).resolve().parents[1]))
