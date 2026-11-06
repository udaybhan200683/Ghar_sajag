#!/usr/bin/env python3
"""One-use, read-only GS-117 active image/partition evidence capture."""
import argparse, binascii, contextlib, hashlib, json, os, platform, re, struct, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

IDF_PARTITION_DIR = r"\\wsl.localhost\Ubuntu\home\udaybhan\.espressif\v6.0.3\esp-idf\components\partition_table"
CHECKPOINT = Path(r"\\wsl.localhost\Ubuntu\home\udaybhan\.local\state\ghar-sajag\gs117-tc001\provenance-refresh-20261031T0501Z\trusted-artifacts")
WSL_AUTHORIZATION_MODULE = "/home/udaybhan/projects/Ghar_sajag_r1/code/tools/local/gs117_hil_authorization.py"
EXPECTED = {
 "c3": {
  "port":"COM4","usb_serial":"14:63:93:C5:D1:58","usb_vid":0x303A,"usb_pid":0x1001,
  "usb_hwid":"USB VID:PID=303A:1001 SER=14:63:93:C5:D1:58 LOCATION=1-1:x.0",
  "mac":"146393c5d158","chip":"ESP32-C3","flash_size":"4MB",
  "artifact":"c3-current-app.bin","version":"gs117-dev-rejoin-20261029",
  "image_size":958992,
  "elf":"043ba7db4a89197e608971a590476ea77807e3abbf58f93e050d3a018dd2f234","image_sha256":"589dc9f98ef78fed97709e2ffb845b0a0eb6ccf5babfd9cc149743539932acb7",
  "partition_table_sha256":"219614d3586ae564ce51dfc462e6e7773b590abe41048a10bc513e1a7d799469","active_partition":"ota_0",
  "layout":{"otadata":(0xF000,0x2000),"ota_0":(0x20000,0x1E0000),"ota_1":(0x200000,0x1E0000)}},
 "s3": {
  "port":"COM10","usb_serial":"E0:72:A1:D3:8D:34","usb_vid":0x303A,"usb_pid":0x1001,
  "usb_hwid":"USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34 LOCATION=1-2:x.0",
  "mac":"e072a1d38d34","chip":"ESP32-S3","flash_size":"16MB",
  "artifact":"s3-current-app.bin","version":"8acab96-dirty",
  "image_size":2292864,
  "elf":"7584a1f80c1a59dc55e7fed9ae3092618cde7c8be8c8ccca6b041e302bf52ed1","image_sha256":"ff1116344cbc05d4c6fcc18a8f003d067b809ef6d90236fd90bba6f86ab052e5",
  "partition_table_sha256":"338f4a83ba90609b4ed0a04514f6378dc90b5d21769e186f49dc3086fd9feabc","active_partition":"ota_1",
  "layout":{"otadata":(0xF000,0x2000),"ota_0":(0x20000,0x400000),"ota_1":(0x420000,0x400000)}}
}

# Exact allowlist for this fixture and the pinned application artifacts. The
# S3 bootloader read is only the fixed 32 KiB region preceding the partition
# table; no caller-supplied offset or size can broaden it.
READ_RANGES = {
 "c3": {
  "partition-table":(0x8000,0x1000),
  "otadata":(0xF000,0x2000),
  "active-app-image":(0x20000,958992),
 },
 "s3": {
  "bootloader-region":(0x000000,0x008000),
  "partition-table":(0x8000,0x1000),
  "otadata":(0xF000,0x2000),
  "active-app-image":(0x420000,2292864),
 },
}

class GuardFailure(Exception): pass
def sha(b): return hashlib.sha256(b).hexdigest()
def sha_file(path):
 h=hashlib.sha256()
 with open(path,"rb") as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b""): h.update(chunk)
 return h.hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()

def claim_authorized_role(role,session_id):
 if not re.fullmatch(r"[0-9a-f]{32}",str(session_id)):
  raise GuardFailure("READBACK_AUTHORIZATION_SESSION_REQUIRED")
 windows_root=os.environ.get("WINDIR",r"C:\\Windows")
 wsl=Path(windows_root)/"System32"/"wsl.exe"
 if not wsl.is_file(): raise GuardFailure("READBACK_AUTHORIZATION_VALIDATOR_UNAVAILABLE")
 sys.path.insert(0,IDF_PARTITION_DIR)
 try:
  import serial, serial.tools.list_ports, esptool, esptool.cmds, esptool.loader
  import gen_esp32part
  from esptool.targets import esp32c3, esp32s3
 except Exception as error:
  raise GuardFailure("READBACK_PINNED_TOOL_IMPORT_FAILED") from error
 if esptool.__version__!="5.4.0": raise GuardFailure("ESPTOOL_VERSION_MISMATCH")
 if (esptool.loader.cfg.get("custom_reset_sequence") is not None or
     esptool.loader.cfg.get("custom_hard_reset_sequence") is not None):
  raise GuardFailure("UNREVIEWED_ESPTOOL_RESET_OVERRIDE")
 runtime_tools={
  "esptool":sha_file(esptool.__file__),
  "esptool_cmds":sha_file(esptool.cmds.__file__),
  "esptool_loader":sha_file(esptool.loader.__file__),
  "esptool_target_c3":sha_file(esp32c3.__file__),
  "esptool_target_s3":sha_file(esp32s3.__file__),
  "pyserial":sha_file(serial.__file__),
  "pyserial_list_ports":sha_file(serial.tools.list_ports.__file__),
  "partition_parser":sha_file(gen_esp32part.__file__),
 }
 command=[str(wsl),"-d","Ubuntu","--","python3",WSL_AUTHORIZATION_MODULE,
          "--claim-readback-receipt-session",session_id,"--role",role,
          "--procedure-sha256",sha_file(__file__),
          "--python-runtime-sha256",sha_file(sys.executable),
          "--python-version",platform.python_version(),
          "--pyserial-version",getattr(serial,"__version__",""),
          "--runtime-tool-hashes-json",json.dumps(runtime_tools,sort_keys=True,separators=(",",":"))]
 try:
  result=subprocess.run(command,capture_output=True,text=True,timeout=20,check=False)
 except (OSError,subprocess.SubprocessError) as error:
  raise GuardFailure("READBACK_AUTHORIZATION_VALIDATION_FAILED") from error
 try: response=json.loads(result.stdout.strip())
 except json.JSONDecodeError: response={}
 if (result.returncode!=0 or response.get("status")!="CLAIMED" or
     response.get("role")!=role or response.get("session_id")!=session_id):
  raise GuardFailure("READBACK_AUTHORIZATION_VALIDATION_FAILED")
 return {"python_version":platform.python_version(),
         "python_executable_sha256":sha_file(sys.executable),
         "runtime_tool_hashes":runtime_tools,
         "esptool_version":esptool.__version__,
         "pyserial_version":getattr(serial,"__version__","")}

def validate_read_range(role,name,offset,size,flash_capacity):
 if role not in READ_RANGES or name not in READ_RANGES[role]:
  raise GuardFailure("READ_REGION_NOT_ALLOWLISTED")
 if type(offset) is not int or type(size) is not int or type(flash_capacity) is not int:
  raise GuardFailure("READ_RANGE_INTEGER_REQUIRED")
 if offset<0 or size<=0 or flash_capacity<=0 or offset>flash_capacity or size>flash_capacity-offset:
  raise GuardFailure(name.upper().replace("-","_")+"_READ_OUT_OF_BOUNDS")
 if (offset,size)!=READ_RANGES[role][name]:
  raise GuardFailure("READ_RANGE_SCOPE_MISMATCH")

def select(raw, app_count):
 copies=[]
 for i in range(2):
  base=i*0x1000
  seq=struct.unpack_from("<I",raw,base)[0]
  state=struct.unpack_from("<I",raw,base+24)[0]
  crc=struct.unpack_from("<I",raw,base+28)[0]
  expected=binascii.crc32(struct.pack("<I",seq),0xFFFFFFFF)&0xFFFFFFFF
  valid=seq!=0xFFFFFFFF and state not in (3,4) and crc==expected
  copies.append({"copy":i,"seq":seq,"state":state,"crc":crc,"crc_valid":crc==expected,"valid":valid})
 valid=[x for x in copies if x["valid"]]
 if not valid: raise GuardFailure("NO_VALID_OTA_SELECTOR")
 chosen=max(valid,key=lambda x:x["seq"])
 if chosen["state"] not in (2,0xFFFFFFFF): raise GuardFailure("SELECTED_OTA_STATE_NOT_STABLE")
 return copies,chosen,(chosen["seq"]-1)%app_count

def artifact(role):
 spec=EXPECTED[role]
 p=CHECKPOINT/spec["artifact"]
 b=p.read_bytes()
 manifest=json.loads((CHECKPOINT/"MANIFEST.json").read_text())
 if (sha(b)!=spec["image_sha256"] or sha(b)!=manifest["files"][spec["artifact"]]["sha256"]): raise GuardFailure("ARTIFACT_MANIFEST_HASH_MISMATCH")
 if len(b)!=spec["image_size"]: raise GuardFailure("ARTIFACT_SIZE_MISMATCH")
 info=(CHECKPOINT/(spec["artifact"]+".image-info.txt")).read_text()
 v=re.search(r"^App version:\s*(\S+)",info,re.M)
 e=re.search(r"^ELF file SHA256:\s*([0-9a-f]{64})",info,re.M)
 if not v or v.group(1)!=spec["version"] or not e or e.group(1)!=spec["elf"]:
  raise GuardFailure("ARTIFACT_PROVENANCE_MISMATCH")
 if "Checksum: " not in info or "(valid)" not in info or "Validation hash: " not in info:
  raise GuardFailure("ARTIFACT_IMAGE_VALIDATION_METADATA_MISSING")
 return b,sha(b),info

def self_test():
 sys.path.insert(0,IDF_PARTITION_DIR)
 import gen_esp32part
 p=Path(r"\\wsl.localhost\Ubuntu\home\udaybhan\projects\Ghar_sajag_r1\docs\hw\evidence\BAT_C8_R1_QUALIFICATION\GS114_C8_EXECUTION_20261013T111655Z\run04_20261014\c3_partition_table_actual.bin")
 table=list(gen_esp32part.PartitionTable.from_binary(p.read_bytes()))
 assert any(x.name=="ota_0" and x.offset==0x20000 for x in table)
 raw=(CHECKPOINT/"s3-verified-postdeploy"/"otadata.bin").read_bytes()
 copies,chosen,slot=select(raw,2)
 assert chosen["valid"] and slot in (0,1)
 for role in EXPECTED:
  b,h,_=artifact(role)
  print(role,"artifact",len(b),h)
 print("READBACK_SCRIPT_SELF_TEST=PASS; NO_SERIAL_PORT_OPENED=YES")

def wait_for_exact_usb(spec, timeout_seconds=12):
 import serial.tools.list_ports
 deadline=time.monotonic()+timeout_seconds
 while time.monotonic()<deadline:
  matches=[p for p in serial.tools.list_ports.comports()
           if p.device==spec["port"] and p.serial_number==spec["usb_serial"] and
           p.hwid==spec["usb_hwid"]]
  same_port=[p for p in serial.tools.list_ports.comports() if p.device==spec["port"]]
  if len(matches)==1 and len(same_port)==1:
   return {"port":matches[0].device,"serial":matches[0].serial_number,"hwid":matches[0].hwid}
  time.sleep(0.2)
 raise GuardFailure("RESTORED_USB_IDENTITY_NOT_REENUMERATED")

def restore_application_once(esp,spec):
 if esp is None:
  raise GuardFailure("APPLICATION_RESTORE_LOADER_UNAVAILABLE")
 port=esp._port
 if not port.is_open:
  port.open()
 # pyserial DTR=False deasserts the active-low line, leaving GPIO0/BOOT HIGH.
 # Pulse EN once with IDF-pinned USB re-enumeration timing. Call the base
 # physical reset method, avoiding a target-specific ROM soft-reset path.
 port.dtr=False
 from esptool.loader import ESPLoader
 ESPLoader.hard_reset(esp,uses_usb=True)
 if port.is_open:
  port.close()
 return wait_for_exact_usb(spec)

def read_flash_region(esp,spec,out,role,name,offset,size,receipt):
 capacity=int(spec["flash_size"].removesuffix("MB"))*1024*1024
 validate_read_range(role,name,offset,size,capacity)
 # This is the direct RAM-stub API, not esptool.cmds.read_flash: the latter
 # detects flash size first and invokes a prohibited flash-ID/JEDEC query.
 data=esp.read_flash(offset,size)
 if not isinstance(data,(bytes,bytearray)) or len(data)!=size:
  raise GuardFailure(name.upper()+"_READ_SIZE_MISMATCH")
 data=bytes(data)
 region_path=out/(role+"-"+name+".bin")
 fd=os.open(region_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,"wb") as saved:
  saved.write(data); saved.flush(); os.fsync(saved.fileno())
 receipt["flash_reads"].append({"region":name,"offset":offset,"size":size,"sha256":sha(data)})
 return data

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--role",choices=("c3","s3"))
 ap.add_argument("--out-dir")
 ap.add_argument("--authorization-session-id")
 ap.add_argument("--self-test",action="store_true")
 a=ap.parse_args()
 if a.self_test: self_test(); return 0
 if not a.role or not a.out_dir or not a.authorization_session_id:
  ap.error("--role, --out-dir, and --authorization-session-id required")
 role=a.role; spec=EXPECTED[role]; out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
 if out.is_symlink() or not out.is_dir() or any(out.iterdir()):
  raise GuardFailure("READBACK_OUTPUT_DIRECTORY_NOT_EMPTY_OR_SAFE")
 os.chmod(out,0o700)
 result=out/(role+"-readback.json"); logpath=out/(role+"-esptool.log")
 r={"role":role,"started_utc":now(),"status":"IN_PROGRESS",
    "scope":"fixture identity, bounded partition table, OTA selector, exact active application bytes; S3 bootloader region only",
    "procedure_sha256":sha(Path(__file__).read_bytes()),
    "port":spec["port"],"expected_usb_serial":spec["usb_serial"],"flash_reads":[],
    "reset_budget":{"rom_loader_entry_max":1,"normal_application_restore_max":1,
                     "connect_attempts":1,"additional_retry_resets":0},
    "rom_loader_entry_attempted":False,
    "application_restoration":{"status":"NOT_REQUIRED_BEFORE_ROM_ENTRY"}}
 esp=None
 operation_failure=None
 rom_entry_attempted=False
 try:
  image,image_sha,info=artifact(role)
  r.update({"trusted_artifact":spec["artifact"],"trusted_artifact_size":len(image),
            "trusted_artifact_sha256":image_sha,"expected_version":spec["version"],"expected_elf_sha256":spec["elf"]})
  r["runtime"] = claim_authorized_role(role,a.authorization_session_id)
  import serial.tools.list_ports
  ports=[p for p in serial.tools.list_ports.comports() if p.device==spec["port"]]
  if len(ports)!=1: raise GuardFailure("EXACT_USB_PORT_NOT_UNIQUE")
  p=ports[0]; r["usb_observed"]={"port":p.device,"serial":p.serial_number,"hwid":p.hwid}
  if (p.serial_number!=spec["usb_serial"] or p.hwid!=spec["usb_hwid"] or
      p.vid!=spec["usb_vid"] or p.pid!=spec["usb_pid"]): raise GuardFailure("EXACT_USB_IDENTITY_MISMATCH")
  sys.path.insert(0,IDF_PARTITION_DIR)
  import gen_esp32part, esptool, esptool.cmds, esptool.loader
  if role=="c3":
   from esptool.targets.esp32c3 import ESP32C3ROM as TargetROM
  else:
   from esptool.targets.esp32s3 import ESP32S3ROM as TargetROM
  with logpath.open("w",encoding="utf-8") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
   # The one reset-aware esptool connection enters ROM download mode. Never use
   # no-reset here: no earlier operation establishes a ROM/stub state.
   esp=TargetROM(spec["port"],baud=115200)
   vid_pid=esp.get_usb_vid_pid()
   r["usb_vid_pid"]=[vid_pid[0],vid_pid[1]]
   if vid_pid!=(spec["usb_vid"],spec["usb_pid"]): raise GuardFailure("ESPLoader_USB_INTERFACE_MISMATCH")
   rom_entry_attempted=True
   r["rom_loader_entry_attempted"]=True
   esp.connect(mode="default-reset",attempts=1)
   r["chip"]=esp.CHIP_NAME
   if esp.CHIP_NAME!=spec["chip"]: raise GuardFailure("CHIP_MODEL_MISMATCH")
   r["mac"]=bytes(esp.read_mac()).hex()
   if r["mac"]!=spec["mac"]: raise GuardFailure("CHIP_MAC_MISMATCH")
   sec=esp.get_security_info(cache=True)
   r["security"]={"secure_boot":bool(sec["parsed_flags"]["SECURE_BOOT_EN"]),
                  "flash_crypt_cnt":int(sec["flash_crypt_cnt"]),
                  "secure_download":bool(sec["parsed_flags"]["SECURE_DOWNLOAD_ENABLE"])}
   if r["security"]["secure_boot"] or r["security"]["flash_crypt_cnt"]!=0 or r["security"]["secure_download"]:
    raise GuardFailure("SECURITY_STATE_MISMATCH")
   r["flash_capacity_requery"]="NOT_PERFORMED_BY_APPROVAL"
   esp=esptool.cmds.run_stub(esp); esp.change_baud(460800)
   if not getattr(esp,"IS_STUB",False): raise GuardFailure("RAM_STUB_REQUIRED_FOR_BOUNDED_READ")
   def read(name,offset,size):
    return read_flash_region(esp,spec,out,role,name,offset,size,r)
   if role=="s3":
    rawboot=read("bootloader-region",*READ_RANGES["s3"]["bootloader-region"])
    r["bootloader_region"]={"offset":"0x000000","size":len(rawboot),
      "sha256":sha(rawboot),
      "digest_scope":"exact bounded flash region 0x000000..0x008000; build/configuration provenance not established by this digest"}
   rawtable=read("partition-table",0x8000,0x1000)
   if sha(rawtable)!=spec["partition_table_sha256"]: raise GuardFailure("PARTITION_TABLE_HASH_MISMATCH")
   parts=list(gen_esp32part.PartitionTable.from_binary(rawtable))
   wanted={}
   for x in parts:
    if x.name in spec["layout"]:
     if x.name in wanted: raise GuardFailure("DUPLICATE_REQUIRED_PARTITION")
     wanted[x.name]=x
   if set(wanted)!=set(spec["layout"]): raise GuardFailure("REQUIRED_PARTITION_SET_MISMATCH")
   for name,(offset,size) in spec["layout"].items():
    x=wanted[name]
    if (x.offset,x.size)!=(offset,size): raise GuardFailure("PARTITION_LAYOUT_MISMATCH_"+name)
    if name=="otadata" and (x.type!=gen_esp32part.DATA_TYPE or x.subtype!=gen_esp32part.SUBTYPES[gen_esp32part.DATA_TYPE]["ota"]):
     raise GuardFailure("OTADATA_TYPE_MISMATCH")
    if name.startswith("ota_") and (x.type!=gen_esp32part.APP_TYPE or x.subtype!=gen_esp32part.MIN_PARTITION_SUBTYPE_APP_OTA+int(name[-1])):
     raise GuardFailure("APP_PARTITION_TYPE_MISMATCH_"+name)
   apps=sorted([x for x in parts if x.type==gen_esp32part.APP_TYPE and
                gen_esp32part.MIN_PARTITION_SUBTYPE_APP_OTA<=x.subtype<
                gen_esp32part.MIN_PARTITION_SUBTYPE_APP_OTA+gen_esp32part.NUM_PARTITION_SUBTYPE_APP_OTA],
               key=lambda x:x.subtype)
   if [x.subtype for x in apps]!=[0x10,0x11]: raise GuardFailure("OTA_SLOT_LAYOUT_MISMATCH")
   rawota=read("otadata",wanted["otadata"].offset,wanted["otadata"].size)
   copies,chosen,slot=select(rawota,len(apps)); active=apps[slot]
   if active.name!=spec["active_partition"]: raise GuardFailure("ACTIVE_APP_PARTITION_MISMATCH")
   r["ota_selector"]={"copies":copies,"selected_copy":chosen["copy"],"selected_seq":chosen["seq"],
      "selected_state":chosen["state"],"active_partition":active.name,"active_slot":slot,
      "active_offset":active.offset,"active_partition_size":active.size}
   if active.encrypted: raise GuardFailure("ACTIVE_APP_PARTITION_ENCRYPTED")
   if len(image)>active.size: raise GuardFailure("TRUSTED_IMAGE_EXCEEDS_ACTIVE_PARTITION")
   rawapp=read("active-app-image",active.offset,len(image))
   r["image_match"]={"readback_size":len(rawapp),"readback_sha256":sha(rawapp),
      "readback_prefix_size":len(rawapp),"readback_prefix_sha256":sha(rawapp),
      "trusted_image_size":len(image),"trusted_image_sha256":image_sha,"byte_for_byte_match":rawapp==image,
      "artifact_image_metadata_sha256":sha(info.encode())}
   if rawapp!=image: raise GuardFailure("ACTIVE_APP_IMAGE_MISMATCH")
 except Exception as exc:
  operation_failure=exc
 finally:
  if rom_entry_attempted:
   r["application_restoration"]={"status":"ATTEMPTED_ONCE",
       "method":"deassert BOOT then one USB-aware EN hard reset; verify exact USB re-enumeration"}
   try:
    with open(os.devnull,"w",encoding="utf-8") as sink:
     with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
      restored=restore_application_once(esp,spec)
    r["application_restoration"]={"status":"USB_IDENTITY_REENUMERATED",
        "device":restored,"runtime_application":"NOT_VERIFIED_BY_READBACK; REQUIRES_BOUNDED_TARGET_OBSERVATION"}
   except Exception as restore_exc:
    r["application_restoration"]={"status":"FAIL","failure":str(restore_exc)[:200]}
    if operation_failure is None:
     operation_failure=GuardFailure("APPLICATION_RESTORE_FAILED")
  if esp is not None:
   try:
    if esp._port.is_open: esp._port.close()
   except Exception as close_exc:
    if operation_failure is None: operation_failure=GuardFailure("SERIAL_CLOSE_FAILED")
  r["completed_utc"]=now()
 if operation_failure is None and r.get("application_restoration",{}).get("status")=="USB_IDENTITY_REENUMERATED" and r.get("image_match",{}).get("byte_for_byte_match") is True:
  r["status"]="PASS"
 else:
  r["status"]="FAIL"
  if operation_failure is not None:
   r["failure"]=str(operation_failure)[:240]
  elif not rom_entry_attempted:
   r["failure"]="READBACK_PRECONDITION_FAILED"
  else:
   r["failure"]="READBACK_OR_RESTORATION_NOT_VERIFIED"
 fd=os.open(result,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,"w",encoding="utf-8") as saved:
  saved.write(json.dumps(r,indent=2)+"\n"); saved.flush(); os.fsync(saved.fileno())
 logpath.chmod(0o600) if logpath.exists() else None
 if r["status"]=="PASS":
  print(json.dumps({"status":"PASS","role":role,"port":spec["port"],"mac":r["mac"],
    "active_partition":r["ota_selector"]["active_partition"],"active_offset":hex(r["ota_selector"]["active_offset"]),
    "image_sha256":r["image_match"]["readback_sha256"],"application_restore":r["application_restoration"]["status"],
    "partition_table_sha256":next(item["sha256"] for item in r["flash_reads"]
                                  if item["region"]=="partition-table")}))
  return 0
 print(json.dumps({"status":"FAIL","role":role,"failure":r["failure"],
                   "application_restore":r["application_restoration"]["status"]}))
 return 2

if __name__=="__main__": raise SystemExit(main())
