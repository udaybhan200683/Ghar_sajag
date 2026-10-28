#!/usr/bin/env python3
"""Clean software-only C3/S3 production-profile build; never opens a serial port."""
from pathlib import Path
import csv, hashlib, json, os, shlex, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from validation.component_gate import source_fingerprint

def slot_size(project,sdkconfig):
    import re
    match=re.search(r'^CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="([^"]+)"',sdkconfig.read_text(),re.M)
    if not match: raise ValueError("missing configured partition file")
    rows=list(csv.reader((project/match.group(1)).read_text().splitlines()))
    apps=[r for r in rows if len(r)>=5 and r[1].strip()=="app" and r[2].strip()=="ota_0"]
    if len(apps)!=1: raise ValueError("missing unique OTA application slot")
    s=apps[0][4].strip()
    return int(s[:-1])*1024 if s.upper().endswith("K") else int(s,0)

def verify_s3_production_profile(build):
    cache=build/"CMakeCache.txt"
    if not cache.is_file(): raise ValueError("S3 production CMake cache missing")
    values={}
    for line in cache.read_text().splitlines():
        if line and not line.startswith(("//","#")) and ":" in line and "=" in line:
            key,value=line.split("=",1)
            values[key.split(":",1)[0]]=value
    expected_off=("GS40_TEST_ONLY_CLOUDSYNC","GS_HIL_BUILD","GS_HIL_CONTROL",
                  "GS_HIL_COMMISSIONING")
    enabled=[key for key in expected_off if values.get(key,"OFF").upper() not in
             {"OFF","0","FALSE","NO"}]
    if enabled: raise ValueError("S3 production profile enabled restricted options: "+",".join(enabled))
    if values.get("GS40_TEST_ONLY_CONFIG_ROOT_DER","").strip():
        raise ValueError("S3 production profile unexpectedly embeds a TEST_ONLY trust root")

def main():
    export=Path(os.environ.get("GS_IDF_EXPORT",str(Path.home()/".espressif/v6.0.3/esp-idf/export.sh")))
    if not export.is_file(): raise ValueError("missing ESP-IDF6.0.3 activation: "+str(export))
    folder=ROOT/"build/validation_targets";folder.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix="gs116-",dir=folder))
    fingerprint=source_fingerprint(extra=["validation/suites.json","validation/component_gate.py",
        "scripts/build_validation_targets.py","tests/python/test_component_gate.py"])
    head=subprocess.check_output(["git","rev-parse","--short=7","HEAD"],cwd=ROOT,text=True).strip()
    version=head+"-gs116-"+fingerprint[:8]
    records={}
    projects=[("c3","esp32c3",ROOT/"firmware/node/target/esp32c3/idf","gs_hw_m1_node"),
              ("s3","esp32s3",ROOT/"firmware/hub/target/esp32s3/idf","gs_r1_s3_hub")]
    asset=work/"assets/node_firmware.bin";asset.parent.mkdir()
    for name,target,project,binary in projects:
        build=work/name
        args=["idf.py","-C",str(project),"-B",str(build),"-D","SDKCONFIG="+str(work/(name+"-sdkconfig")),
              "-D","IDF_TARGET="+target,"-D","PROJECT_VER="+version,
              "-D","GS_HIL_BUILD=OFF","-D","GS_HIL_CONTROL=OFF"]
        if name=="s3":
            args += ["-D","GS40_TEST_ONLY_CLOUDSYNC=OFF",
                     "-D","GS_HIL_COMMISSIONING=OFF"]
        if name=="s3": args+=["-D","GS_NODE_FIRMWARE_ASSET="+str(asset)]
        args+=["build","size"]
        shell="source "+shlex.quote(str(export))+" >/dev/null 2>&1 && idf.py --version && "+shlex.join(args)
        log=work/(name+".log")
        build_env={**os.environ,"IDF_PY_BUILD_JOBS":os.environ.get("IDF_PY_BUILD_JOBS","2")}
        if name=="s3":
            # IDF component requirement discovery may evaluate the component
            # CMake file before the root -D cache definition is visible. Pass
            # the same validated paired image through the inherited build
            # environment as well; CMake keeps the existing source-tree
            # default when this variable is absent.
            build_env["GS_NODE_FIRMWARE_ASSET"]=str(asset)
        with log.open("w") as f:
            rc=subprocess.run(["bash","-c",shell],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,
                env=build_env,timeout=1800).returncode
        if rc or "ESP-IDF v6.0.3" not in log.read_text(): raise ValueError(name+" build/version failed: "+str(log))
        if name=="s3": verify_s3_production_profile(build)
        image=build/(binary+".bin");data=image.read_bytes()
        capacity=slot_size(project,work/(name+"-sdkconfig"))
        if len(data)>capacity: raise ValueError(name+" application exceeds OTA slot")
        description=json.loads((build/"project_description.json").read_text())
        if description["project_version"]!=version: raise ValueError("stale/wrong target metadata")
        records[name]={"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data),
                       "slot_bytes":capacity,"build":str(build),"version":version,"command":args}
        if name=="c3": asset.write_bytes(data)
        print(name,"BUILD PASS",len(data),"bytes",flush=True)
    bundle=work/"bundle"
    subprocess.run([sys.executable,"scripts/package_node_health_firmware.py","--c3-build",str(work/"c3"),
        "--s3-build",str(work/"s3"),"--output",str(bundle)],cwd=ROOT,check=True,
        stdout=(work/"package.log").open("w"))
    report={"source_head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        "source_fingerprint":fingerprint,
        "profile":"production GS40_TEST_ONLY_CLOUDSYNC=OFF GS_HIL_BUILD=OFF GS_HIL_CONTROL=OFF GS_HIL_COMMISSIONING=OFF",
        "test_only_pathways":"VERIFIED_DISABLED",
        "idf_version":"6.0.3","images":records,"physical_status":"NOT_RUN",
        "hardware_actions":"NONE","qualification":"TARGET_COMPILED_ONLY"}
    (work/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    print("TARGET REPORT",work/"report.json")
    print("VALIDATION TARGET BUILDS PASS")
    return 0
if __name__=="__main__":
    try: raise SystemExit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print("VALIDATION TARGET BUILDS FAIL:",error,file=sys.stderr);raise SystemExit(1)
