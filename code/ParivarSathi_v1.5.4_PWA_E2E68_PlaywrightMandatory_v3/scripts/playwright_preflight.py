#!/usr/bin/env python3
import shutil, subprocess, sys
missing=[]
for cmd in ("node","npm","npx"):
    if not shutil.which(cmd): missing.append(cmd)
if missing:
    print("FAIL: missing required commands:", ", ".join(missing))
    print("Install Node.js/npm, then run: make playwright-install")
    raise SystemExit(2)
try:
    subprocess.run(["npx","playwright","--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
except Exception:
    print("FAIL: Playwright is not installed. Run: make playwright-install")
    raise SystemExit(2)
print("PASS: Playwright preflight")
