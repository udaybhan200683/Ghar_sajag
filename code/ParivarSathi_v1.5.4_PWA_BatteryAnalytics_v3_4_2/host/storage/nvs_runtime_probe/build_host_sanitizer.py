#!/usr/bin/env python3
"""Instrument isolated probe/main (including offline header); SDK archives unchanged."""
from pathlib import Path
import argparse
import shlex
import subprocess

here=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
commands=subprocess.check_output(['ninja','-t','commands','gs_nvs_runtime_probe.elf'],cwd=here/'build',text=True).splitlines()
compile_line=next(x for x in commands if '/main/probe.cpp' in x and ' -c ' in x)
compile_args=shlex.split(compile_line)
obj=a.output.resolve()/'probe.o'
compile_args[compile_args.index('-o')+1]=str(obj)
compile_args+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
link_line=next(x for x in commands if ' -o gs_nvs_runtime_probe.elf ' in x)
link_args=shlex.split(link_line.split(' && ')[1])
link_args[link_args.index('-o')+1]=str(a.output.resolve()/'probe.elf')
link_args.insert(1,str(obj));link_args+=['-fsanitize=address,undefined']
for cmd in (compile_args,link_args):
 print('COMMAND='+shlex.join(cmd),flush=True)
 r=subprocess.run(cmd,cwd=here/'build')
 print('EXIT='+str(r.returncode),flush=True);assert r.returncode==0
print('SANITIZER_SCOPE=isolated probe/main + offline header only; SDK archives uninstrumented; LeakSanitizer disabled during run')
