"""Build existing production host fixture with only an owned-temp environment adapter.

Explicit review preparation, not a new validation framework or acceptance stage.
No product/source/registry edits. All outputs are isolated under code/build.
"""
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
temporary = ROOT / "build/dashboard_review_tmp"
temporary.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, TMPDIR=str(temporary))
lines = subprocess.check_output(["make", "-n", "p0-board-stack-event-host-test"], text=True).splitlines()
argv = shlex.split(next(line for line in lines if " -o build/p0_board_stack_e2e_validation" in line))
objects = [item for item in argv if item.endswith(".o")]
subprocess.run(["make", "-j2", "build", *objects], env=env, check=True)
argv[1:1] = ["-include", "tests/support/engineering_dashboard_review/owned_temp_adapter.hpp"]
argv[argv.index("-o") + 1] = "build/dashboard_review_host_event"
print("CLASSIFICATION=TEST_INFRA_ONLY environment_adapter=OWNED_TMP source_edits=NONE", flush=True)
print(shlex.join(argv), flush=True)
subprocess.run(argv, env=env, check=True)
command = [str(ROOT / "build/dashboard_review_host_event"), "--emit-p0-event",
           "build/p0_product_event.json", "build/p0_cloud_sync_request.json"]
print(shlex.join(command), flush=True)
subprocess.run(command, env=env, check=True)
subprocess.run([str(ROOT / "build/dashboard_review_host_event")], env=env, check=True)
