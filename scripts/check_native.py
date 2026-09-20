"""Compile generated C++ and compare its JSON measurements to the builder."""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engine import decode_image, detect
from backend.exporter import export_cpp
from backend.models import ExportRequest, Measurements, Strategy

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
NATIVE = ROOT / "artifacts/native"
NATIVE.mkdir(parents=True, exist_ok=True)
manifest = json.loads((ROOT / "examples/manifest.json").read_text())
cmake = ROOT / ".venv/Lib/site-packages/cmake/data/bin/cmake.exe"
ninja = ROOT / ".venv/Scripts/ninja.exe"
env = os.environ.copy()
env["ZIG_GLOBAL_CACHE_DIR"] = str(TOOLS / "zig-cache")
env["ZIG_LOCAL_CACHE_DIR"] = str(TOOLS / "zig-local-cache")
env["PATH"] = str(ROOT / ".venv/Scripts") + os.pathsep + env["PATH"]
measures = Measurements(fields=["length","width","area","angle","color","center"])
cmake_text = ['cmake_minimum_required(VERSION 3.16)', 'project(export_checks LANGUAGES CXX)',
              'find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs)']
cases = []
for example in manifest:
    for index, config in enumerate(example["strategies"]):
        name = example["id"].replace("-", "_") + "_" + str(index)
        strategy = Strategy(**config)
        request = ExportRequest(strategy=strategy, measurements=measures)
        with zipfile.ZipFile(io.BytesIO(export_cpp(request))) as z:
            (NATIVE / f"{name}.cpp").write_bytes(z.read("detector.cpp"))
        cmake_text.extend([f'add_executable({name} {name}.cpp)', f'target_compile_features({name} PRIVATE cxx_std_17)',
                           f'target_include_directories({name} PRIVATE ${{OpenCV_INCLUDE_DIRS}})',
                           f'target_link_libraries({name} PRIVATE ${{OpenCV_LIBS}})'])
        cases.append((name, example, strategy, measures))
# Also exercise calibrated measurements and selective output fields.
name = "calibrated"
calibrated = Measurements(fields=["length","width","area"],pixels_per_unit=10,unit="mm")
strategy = Strategy(**manifest[0]["strategies"][0])
with zipfile.ZipFile(io.BytesIO(export_cpp(ExportRequest(strategy=strategy,measurements=calibrated)))) as z:
    (NATIVE / f"{name}.cpp").write_bytes(z.read("detector.cpp"))
cmake_text.extend([f'add_executable({name} {name}.cpp)', f'target_compile_features({name} PRIVATE cxx_std_17)',
                   f'target_include_directories({name} PRIVATE ${{OpenCV_INCLUDE_DIRS}})',
                   f'target_link_libraries({name} PRIVATE ${{OpenCV_LIBS}})'])
cases.append((name,manifest[0],strategy,calibrated))
(NATIVE / "CMakeLists.txt").write_text("\n".join(cmake_text))
build = NATIVE / "build"
subprocess.run([str(cmake),"-S",str(NATIVE),"-B",str(build),"-G","Ninja","-DCMAKE_BUILD_TYPE=Release",
                f"-DCMAKE_MAKE_PROGRAM={ninja.as_posix()}",f"-DOpenCV_DIR={(TOOLS/'opencv-build').as_posix()}",
                f"-DCMAKE_CXX_COMPILER={(TOOLS/'cxx.cmd').as_posix()}"],env=env,check=True)
subprocess.run([str(cmake),"--build",str(build),"--parallel","2"],env=env,check=True)
report=[]
for name, example, strategy, measurement in cases:
    image_path=ROOT/"examples"/example["filename"]
    image=decode_image("data:image/png;base64,"+base64.b64encode(image_path.read_bytes()).decode())
    expected=detect(image,strategy,measurement)
    binary=build/f"{name}.exe"
    actual=json.loads(subprocess.check_output([str(binary),str(image_path)],text=True,env=env))
    assert actual["count"]==expected["count"],(name,actual["count"],expected["count"])
    assert actual["unit"]==expected["unit"]
    for a,b in zip(actual["detections"],expected["detections"]):
        assert all(abs(x-y)<.05 for x,y in zip(a["box"],b["box"])),(name,"box",a,b)
        assert a["measurements"].keys()==b["measurements"].keys()
        for key,value in b["measurements"].items():
            other=a["measurements"][key]
            if value is None: assert other is None,(name,key,other,value)
            elif isinstance(value,str): assert other==value,(name,key,other,value)
            elif isinstance(value,list): assert all(abs(x-y)<.05 for x,y in zip(value,other)),(name,key,other,value)
            else: assert abs(other-value)<.1,(name,key,other,value)
    entry={"case":name,"count":actual["count"],"cpp_latency_ms":actual["latency_ms"],"binary_bytes":binary.stat().st_size,"parity":"passed"}
    report.append(entry)
    print(json.dumps(entry),flush=True)
failure=subprocess.run([str(build/"red_candies_0.exe"),"missing-image.png"],capture_output=True,text=True)
assert failure.returncode==1 and not failure.stdout
(ROOT/"artifacts/native-parity.json").write_text(json.dumps(report,indent=2))
print(f"Passed {len(report)} compiled C++ parity cases and missing-file handling.")
