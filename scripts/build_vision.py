"""Build the small CImg CPU bridge with CMake and an installed C++ compiler."""
import os, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def build():
    bundled=ROOT/'.venv/Lib/site-packages/cmake/data/bin/cmake.exe'
    cmake=str(bundled) if bundled.exists() else shutil.which('cmake')
    if not cmake:raise RuntimeError('Install CMake and a C++17 compiler, then run python scripts/build_vision.py')
    env=os.environ.copy();args=[cmake,'-S',str(ROOT/'backend/vendor'),'-B',str(ROOT/'artifacts/cimg-build'),'-DCMAKE_BUILD_TYPE=Release']
    compiler=ROOT/'.tools/cxx.cmd'
    if compiler.exists():
        env['ZIG_GLOBAL_CACHE_DIR']=str(ROOT/'.tools/zig-cache');env['ZIG_LOCAL_CACHE_DIR']=str(ROOT/'.tools/zig-local-cache')
        args+=['-G','Ninja',f'-DCMAKE_CXX_COMPILER={compiler.as_posix()}',f'-DCMAKE_MAKE_PROGRAM={(ROOT/".venv/Scripts/ninja.exe").as_posix()}']
    subprocess.run(args,check=True,env=env)
    subprocess.run([cmake,'--build',str(ROOT/'artifacts/cimg-build'),'--config','Release','--parallel','2'],check=True,env=env)

if __name__=='__main__':build()
