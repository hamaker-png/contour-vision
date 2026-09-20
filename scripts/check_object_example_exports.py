"""Build actual API-downloaded object-example ZIPs and compare them with saved projects.

Run scripts/check_object_examples.py against the local app first, then:
    python scripts/check_object_example_exports.py
    python scripts/check_object_example_exports.py --ids b-solder-pads b-pills a-washers

Uses the project-local Windows portable compiler and OpenCV build. No export is
regenerated, no API/model call is made, and application source is not changed.
Artifacts are retained under artifacts/object-example-native/<id>.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import stat
import subprocess
import sys
import zipfile

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.engine import counts,decode_image
from backend.graph_exporter import validate_export_graph
from backend.models import Measurements,Sample
from backend.search_execution import execute
from backend.timeline_exporter import TimelineExportRequest
from backend.timelines import Timeline

INPUT=ROOT/'artifacts/object-examples'
OUTPUT=ROOT/'artifacts/object-example-native'

def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def sha(data):return hashlib.sha256(data).hexdigest()

def safe_extract(archive,directory):
    directory=directory.resolve()
    if sum(info.file_size for info in archive.infolist())>200*1024*1024:
        raise ValueError('Export expands beyond 200 MiB')
    if len(archive.infolist())>10000:raise ValueError('Too many export archive entries')
    seen=set()
    for info in archive.infolist():
        name=info.filename
        relative=PurePosixPath(name)
        if '\\' in name or ':' in name or relative.is_absolute() or '..' in relative.parts:
            raise ValueError(f'Unsafe export member: {name}')
        target=(directory/Path(*relative.parts)).resolve()
        if not target.is_relative_to(directory) or target==directory:
            raise ValueError(f'Unsafe export member: {name}')
        if stat.S_ISLNK(info.external_attr>>16):raise ValueError(f'Export contains a symlink: {name}')
        normalized=str(target).casefold()
        if normalized in seen:raise ValueError(f'Duplicate export path: {name}')
        seen.add(normalized)
        if info.is_dir():continue
        target.parent.mkdir(parents=True,exist_ok=True)
        data=archive.read(info)
        if not target.exists() or target.read_bytes()!=data:target.write_bytes(data)

def compare_measurements(actual,expected,label):
    assert len(actual)==len(expected),(label,'measurement-stage count',len(actual),len(expected))
    fields_checked=0
    for native,(identifier,python) in zip(actual,expected,strict=True):
        assert native['id']==identifier,(label,'measurement order',native['id'],identifier)
        assert native['count']==python['count'],(label,identifier,'object count')
        assert native['unit']==python['unit'],(label,identifier,'units')
        if 'measurement_basis' in native:
            assert native['measurement_basis']==python['measurement_basis'],(label,identifier,'measurement basis')
        assert len(native['detections'])==len(python['detections'])==python['count']
        for index,(observed,truth) in enumerate(zip(native['detections'],python['detections'],strict=True)):
            assert np.allclose(observed['box'],truth['box'],atol=.002,rtol=0),(label,identifier,index,'box',observed['box'],truth['box'])
            assert observed['measurements'].keys()==truth['measurements'].keys(),(label,identifier,index,'measurement keys')
            for field,value in truth['measurements'].items():
                got=observed['measurements'][field]
                if isinstance(value,str) or value is None:
                    assert got==value,(label,identifier,index,field,got,value)
                else:
                    assert np.allclose(got,value,atol=.02,rtol=0),(label,identifier,index,field,got,value)
                fields_checked+=1
    return fields_checked

def check_family(identifier,catalog,env,cmake):
    source_directory=INPUT/identifier
    zip_path=source_directory/'selected-cpp.zip'
    project_path=source_directory/(identifier+'.json')
    if not zip_path.is_file() or not project_path.is_file():
        raise ValueError(f'Missing API artifacts for {identifier}; run scripts/check_object_examples.py first.')
    project_bytes=project_path.read_bytes()
    project=json.loads(project_bytes.decode('utf-8'))
    graphs=[Timeline.model_validate(row) for row in project['timelines']]
    measurements=Measurements.model_validate(project['measurements'])
    samples=[Sample.model_validate(row) for row in project['samples']]
    assert len(samples)==3,(identifier,'expected all three family samples')
    definition=catalog[identifier]
    selected=definition['recommended_timeline_id']
    request=TimelineExportRequest(timelines=graphs,selected_timeline_id=selected,measurements=measurements)
    resolved,order,previous,kinds=validate_export_graph(request)
    ids=[operation.id for operation in order]
    assert len(ids)==len(set(ids)),(identifier,'duplicate shared operation in execution order')
    assert [sample.id for sample in samples]==[row['id'] for row in definition['samples']]
    expected_samples={row['id']:row for row in definition['samples']}
    directory=OUTPUT/identifier
    directory.mkdir(parents=True,exist_ok=True)
    package=zip_path.read_bytes()
    (directory/'selected-cpp.zip').write_bytes(package)
    (directory/'saved-project.json').write_bytes(project_bytes)
    with zipfile.ZipFile(zip_path) as archive:
        config=json.loads(archive.read('config.json').decode('utf-8'))
        assert config['selected_timeline_id']==selected,(identifier,'wrong exported pipeline')
        assert config['operations']==[operation.model_dump() for operation in order],(identifier,'compiled operations/parameters differ from saved graph')
        assert config['measurements']==measurements.model_dump(),(identifier,'compiled measurements differ from saved project')
        if 'selected_path' in config:
            assert config['selected_path']==[operation.id for operation in resolved[selected]]
        safe_extract(archive,directory)
    configure=[str(cmake),'-S',str(directory),'-B',str(directory/'build'),'-G','Ninja','-DCMAKE_BUILD_TYPE=Release',
        f'-DCMAKE_MAKE_PROGRAM={(ROOT/".venv/Scripts/ninja.exe").as_posix()}',
        f'-DCMAKE_CXX_COMPILER={(ROOT/".tools/cxx.cmd").as_posix()}',
        f'-DCMAKE_C_COMPILER={(ROOT/".tools/cc.cmd").as_posix()}',
        f'-DCMAKE_AR={(ROOT/".tools/ar.cmd").as_posix()}',
        f'-DCMAKE_RANLIB={(ROOT/".tools/ranlib.cmd").as_posix()}',
        f'-DOpenCV_DIR={(ROOT/".tools/opencv-build").as_posix()}']
    for phase,command in [('configure',configure),('build',[str(cmake),'--build',str(directory/'build'),'--parallel','2'])]:
        outcome=subprocess.run(command,env=env,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=180)
        (directory/(phase+'.log')).write_text(outcome.stdout+outcome.stderr,encoding='utf-8')
        if outcome.returncode:raise RuntimeError(f'{identifier} {phase} failed; see {directory/(phase+".log")}')
    binary=directory/'build/detector.exe'
    records=[]
    for sample in samples:
        source=decode_image(sample.data)
        prefix,payload=sample.data.split(',',1)
        extension={ 'data:image/png;base64':'png','data:image/jpeg;base64':'jpg','data:image/webp;base64':'webp'}[prefix]
        input_path=directory/(sample.id+'-input.'+extension)
        input_path.write_bytes(base64.b64decode(payload,validate=True))
        trace={}
        final,_=execute(source,graphs,selected,measurements,trace=trace,trace_ids=ids)
        expected=[(operation.id,trace[operation.id][0].details) for operation in order if 'detections' in trace[operation.id][0].details]
        output=directory/(sample.id+'-final.png')
        preview=directory/(sample.id+'-preview.png')
        completed=subprocess.run([str(binary),'--output',str(output),'--preview',str(preview),str(input_path)],
            env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15)
        (directory/(sample.id+'-stderr.txt')).write_text(completed.stderr,encoding='utf-8')
        if completed.returncode:raise RuntimeError(f'{identifier}/{sample.id}: {completed.stderr}')
        actual=json.loads(completed.stdout)
        write_json(directory/(sample.id+'-native.json'),actual)
        write_json(directory/(sample.id+'-python-measurements.json'),[{'id':node,**details} for node,details in expected])
        pixels=cv2.imread(str(output),cv2.IMREAD_UNCHANGED)
        assert pixels is not None and pixels.shape==final.image.shape,(identifier,sample.id,'final image shape')
        differences=int(np.count_nonzero(pixels!=final.image))
        assert differences==0,(identifier,sample.id,'final pixels',differences)
        assert [(row['id'],row['kind']) for row in actual['operations']]==[(operation.id,operation.kind) for operation in order],(identifier,sample.id,'executed dependency order')
        assert actual['final']==dict(kind=final.kind,width=final.image.shape[1],height=final.image.shape[0])
        assert kinds[resolved[selected][-1].id]==final.kind
        checked=compare_measurements(actual['measurement_steps'],expected,(identifier,sample.id))
        expected_count=expected_samples[sample.id]['expected_count']
        tp,fp,fn=counts(final.details.get('detections',[]),sample)
        assert (tp,fp,fn)==(expected_count,0,0),(identifier,sample.id,'labeled detection outcome',tp,fp,fn)
        records.append(dict(sample_id=sample.id,expected_count=expected_count,final_count=final.details.get('count'),
            tp=tp,fp=fp,fn=fn,final_pixel_differences=differences,measurement_stages=len(expected),
            measurement_fields_checked=checked,matching_measurements=True,operation_order=ids,
            single_native_ms=actual['latency_ms'],input_sha256=sha(input_path.read_bytes())))
        print(f'{identifier}/{sample.id}: exact final pixels, {len(expected)} measurement stages matched',flush=True)
    result=dict(id=identifier,recorded_utc=datetime.now(timezone.utc).isoformat(),passed=True,
        downloaded_zip=str(zip_path),downloaded_zip_sha256=sha(package),saved_project_sha256=sha(project_bytes),
        binary_sha256=sha(binary.read_bytes()),binary_bytes=binary.stat().st_size,selected_timeline_id=selected,
        exact_configuration=True,unique_operations=len(ids),operation_kinds=[operation.kind for operation in order],
        selected_path=[operation.id for operation in resolved[selected]],samples=records,
        tolerances=dict(final_pixels=0,box_absolute=.002,numeric_measurement_absolute=.02,strings_and_null='exact'),
        limitations='Three constructed teaching samples per program. Native timings are single local runs; this is parity evidence, not real-world accuracy or deployment throughput.')
    write_json(directory/'report.json',result)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--ids',nargs='+',default=['b-solder-pads','b-pills','a-washers'])
    args=parser.parse_args()
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+',value) for value in args.ids):parser.error('Example IDs must contain only letters, digits, hyphens or underscores')
    if len(set(args.ids))!=len(args.ids):parser.error('Choose distinct example IDs')
    catalog={}
    for name in ('object-tests-a.json','object-tests-b.json','object-tests-photos.json'):
        path=ROOT/'examples'/name
        if path.exists():
            catalog.update({entry['id']:entry for entry in json.loads(path.read_text(encoding='utf-8'))})
    for identifier in args.ids:
        if identifier not in catalog:parser.error(f'Unknown example ID: {identifier}')
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','ZIG_GLOBAL_CACHE_DIR':str(ROOT/'.tools/zig-cache'),'ZIG_LOCAL_CACHE_DIR':str(ROOT/'.tools/zig-local-cache')}
    cmake=ROOT/'.venv/Lib/site-packages/cmake/data/bin/cmake.exe'
    OUTPUT.mkdir(parents=True,exist_ok=True)
    results=[]
    for identifier in args.ids:results.append(check_family(identifier,catalog,env,cmake))
    summary=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),programs=len(results),
        image_cases=sum(len(row['samples']) for row in results),passed=True,examples=results)
    write_json(OUTPUT/'report.json',summary)
    print(json.dumps({key:summary[key] for key in ('programs','image_cases','passed')},indent=2),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
