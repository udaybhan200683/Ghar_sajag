#!/usr/bin/env python3
"""Execute board E2E then prove injected failure and zero selection fail."""
import os
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
subprocess.run(['make','board-stack-e2e-host-test'],cwd=ROOT,check=True)
binary=ROOT/'build/board_stack_e2e_validation'
for args,env,expected,marker in [
    ([str(binary),'BOARD-TC-130-001'],{**os.environ,'GS_BOARD_E2E_INJECT_FAILURE':'BOARD-TC-130-001'},1,'controlled board-stack negative self-test'),
    ([str(binary),'NO-SUCH-TEST'],dict(os.environ),2,'zero selected board cases')]:
    result=subprocess.run(args,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if result.returncode!=expected or marker not in result.stdout:
        raise SystemExit('board negative self-test FAILED: '+result.stdout)
print('BOARD E2E NEGATIVE PASS checks=2')
