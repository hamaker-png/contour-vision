"""Build the actual browser-downloaded ZIPs and compare their selected path to Python."""
import json,os,subprocess,sys,zipfile
from pathlib import Path
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.engine import decode_image
from backend.models import Measurements
from backend.timelines import Frame,Timeline,apply_operation,resolve_paths

evidence=json.loads((ROOT/'artifacts/strict/round-10-export.json').read_text())
dest=ROOT/'artifacts/strict/browser-native';dest.mkdir(parents=True,exist_ok=True)
cmake=['cmake_minimum_required(VERSION 3.16)','project(browser_exports LANGUAGES CXX)','find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs)']
cases=[]
for name,folder in evidence['exportDirs'].items():
    directory=Path(folder);request=json.loads((directory/'export-request.json').read_text());workspace=json.loads((directory/'expected-workspace.json').read_text())
    graph=[Timeline.model_validate(t) for t in request['timelines']];path=resolve_paths(graph)[request['selected_timeline_id']];measures=Measurements.model_validate(request['measurements'])
    with zipfile.ZipFile(directory/'timeline-detector.zip') as archive:
        config=json.loads(archive.read('config.json'))
        assert config['operations']==[op.model_dump() for op in path],(name,'exact flattened order and parameters')
        assert config['measurements']==measures.model_dump(),(name,'measurements')
        (dest/f'{name}.cpp').write_bytes(archive.read('detector.cpp'))
    cmake += [f'add_executable({name} {name}.cpp)',f'target_compile_features({name} PRIVATE cxx_std_17)',f'target_include_directories({name} PRIVATE ${{OpenCV_INCLUDE_DIRS}})',f'target_link_libraries({name} PRIVATE ${{OpenCV_LIBS}})']
    cases.append((name,workspace['samples'][0],path,measures))
(dest/'CMakeLists.txt').write_text('\n'.join(cmake))
env=os.environ.copy();env['ZIG_GLOBAL_CACHE_DIR']=str(ROOT/'.tools/zig-cache');env['ZIG_LOCAL_CACHE_DIR']=str(ROOT/'.tools/zig-local-cache');env['PATH']=str(ROOT/'.venv/Scripts')+os.pathsep+env['PATH']
cmakebin=ROOT/'.venv/Lib/site-packages/cmake/data/bin/cmake.exe';build=dest/'build'
subprocess.run([str(cmakebin),'-S',str(dest),'-B',str(build),'-G','Ninja','-DCMAKE_BUILD_TYPE=Release',f'-DCMAKE_MAKE_PROGRAM={(ROOT/".venv/Scripts/ninja.exe").as_posix()}',f'-DOpenCV_DIR={(ROOT/".tools/opencv-build").as_posix()}',f'-DCMAKE_CXX_COMPILER={(ROOT/".tools/cxx.cmd").as_posix()}'],env=env,check=True)
subprocess.run([str(cmakebin),'--build',str(build),'--parallel','2'],env=env,check=True)
records=[]
for name,sample,path,measures in cases:
    source=decode_image(sample['data']);frame=Frame(source,'color');expected=[]
    for op in path:
        frame=apply_operation(frame,op,source,measures)
        if 'detections' in frame.details:expected.append((op.id,frame.details))
    input_path=dest/f'{name}-input.png';cv2.imwrite(str(input_path),source)
    output=dest/f'{name}-final.png';binary=build/f'{name}.exe'
    actual=json.loads(subprocess.check_output([str(binary),'--output',str(output),str(input_path)],env=env,text=True))
    pixels=cv2.imread(str(output),cv2.IMREAD_UNCHANGED);assert pixels.shape==frame.image.shape
    differences=int(np.count_nonzero(pixels!=frame.image));assert not differences,(name,'final pixels',differences)
    assert len(actual['measurement_steps'])==len(expected)
    for observed,(opid,truth) in zip(actual['measurement_steps'],expected):
        assert observed['id']==opid and observed['count']==truth['count'] and observed['unit']==truth['unit']
        for a,b in zip(observed['detections'],truth['detections']):
            assert np.allclose(a['box'],b['box'],atol=.01,rtol=0)
            assert a['measurements'].keys()==b['measurements'].keys()
            for key,value in b['measurements'].items():
                if value is None:assert a['measurements'][key] is None
                else:assert np.allclose(a['measurements'][key],value,atol=.05,rtol=0),(name,key,a,value)
    record={'case':name,'downloaded_zip':str(Path(evidence['exportDirs'][name])/'timeline-detector.zip'),'operation_ids':[op.id for op in path],'operations':[op.kind for op in path],'unit':actual['measurement_steps'][-1]['unit'],'detections':actual['measurement_steps'][-1]['count'],'exact_configuration':True,'final_pixel_differences':differences,'measurement_parity':True,'binary_bytes':binary.stat().st_size,'latency_ms':actual['latency_ms']}
    records.append(record);print(json.dumps(record),flush=True)
(ROOT/'artifacts/strict/browser-export-parity.json').write_text(json.dumps(records,indent=2))
