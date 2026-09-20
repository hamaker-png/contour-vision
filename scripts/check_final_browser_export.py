"""Compile the actual final browser download and compare every detector with Python.

Requires artifacts/night-final-browser/{pipeline-detector.zip,export-request.json,
contour-workspace.json}, the local Windows native toolchain, and Python dependencies.
The original ZIP is never regenerated. Replaying the saved project uses its exact image.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.engine import decode_image
from backend.timeline_exporter import TimelineExportRequest
from backend.timelines import Frame, apply_operation, execution_plan, resolve_paths
from backend.vision_ops import confirm_frame
from backend.vision_params import supporting_ids

evidence = ROOT / 'artifacts/night-final-browser'
directory = evidence / 'native'
directory.mkdir(parents=True, exist_ok=True)
request = TimelineExportRequest.model_validate_json((evidence / 'export-request.json').read_text(encoding='utf-8'))
project = json.loads((evidence / 'contour-workspace.json').read_text(encoding='utf-8'))
package = evidence / 'pipeline-detector.zip'
order, previous, _ = execution_plan(request.timelines, request.selected_timeline_id)
resolved = resolve_paths(request.timelines)
with zipfile.ZipFile(package) as archive:
    config = json.loads(archive.read('config.json'))
    assert config['selected_timeline_id'] == request.selected_timeline_id
    assert config['operations'] == [operation.model_dump() for operation in order]
    assert config['measurements'] == request.measurements.model_dump()
    for info in archive.infolist():
        if info.is_dir():
            continue
        target = (directory / info.filename).resolve()
        if not target.is_relative_to(directory.resolve()):
            raise ValueError('Unsafe archive member')
        target.parent.mkdir(parents=True, exist_ok=True)
        data = archive.read(info)
        if not target.exists() or target.read_bytes() != data:
            target.write_bytes(data)

env = {**os.environ, 'ZIG_GLOBAL_CACHE_DIR': str(ROOT / '.tools/zig-cache'),
       'ZIG_LOCAL_CACHE_DIR': str(ROOT / '.tools/zig-local-cache')}
cmake = str(ROOT / '.venv/Lib/site-packages/cmake/data/bin/cmake.exe')
build = directory / 'build'
configure = [cmake, '-S', str(directory), '-B', str(build), '-G', 'Ninja',
             '-DCMAKE_BUILD_TYPE=Release',
             f'-DCMAKE_MAKE_PROGRAM={(ROOT / ".venv/Scripts/ninja.exe").as_posix()}',
             f'-DCMAKE_CXX_COMPILER={(ROOT / ".tools/cxx.cmd").as_posix()}',
             f'-DOpenCV_DIR={(ROOT / ".tools/opencv-build").as_posix()}']
subprocess.run(configure, env=env, check=True)
subprocess.run([cmake, '--build', str(build), '--parallel', '2'], env=env, check=True)
binary = build / 'detector.exe'
records = []
for index, sample in enumerate(project['samples']):
    source = decode_image(sample['data'])
    input_path = directory / f'input-{index}.png'
    input_path.write_bytes(base64.b64decode(sample['data'].split(',', 1)[1]))
    frames = {'source': Frame(source, 'color')}
    expected = []
    for operation in order:
        frame = frames[previous[operation.id]]
        if operation.kind == 'confirm':
            frame = confirm_frame(frame, [(tid, frames[resolved[tid][-1].id]) for tid in supporting_ids(operation)],
                                  operation.params, source, request.measurements)
        else:
            frame = apply_operation(frame, operation, source, request.measurements)
        frames[operation.id] = frame
        if 'detections' in frame.details:
            expected.append((operation.id, frame.details))
    final = frames[resolved[request.selected_timeline_id][-1].id]
    output = directory / f'final-{index}.png'
    preview = directory / f'preview-{index}.png'
    actual = json.loads(subprocess.check_output([str(binary), '--output', str(output),
                        '--preview', str(preview), str(input_path)], text=True, encoding='utf-8', timeout=20))
    assert [step['id'] for step in actual['operations']] == [operation.id for operation in order]
    assert np.array_equal(cv2.imread(str(output), cv2.IMREAD_UNCHANGED), final.image)
    assert final.preview is not None and np.array_equal(cv2.imread(str(preview)), final.preview)
    assert len(actual['measurement_steps']) == len(expected)
    for observed, (operation_id, truth) in zip(actual['measurement_steps'], expected):
        assert observed['id'] == operation_id and observed['count'] == truth['count']
        assert observed['unit'] == truth['unit']
        for detection, correct in zip(observed['detections'], truth['detections']):
            assert np.allclose(detection['box'], correct['box'], atol=.002, rtol=0)
            assert detection['measurements'].keys() == correct['measurements'].keys()
            for key, value in correct['measurements'].items():
                if isinstance(value, str) or value is None:
                    assert detection['measurements'][key] == value
                else:
                    assert np.allclose(detection['measurements'][key], value, atol=.02, rtol=0), key
    (directory / f'result-{index}.json').write_text(json.dumps(actual, indent=2), encoding='utf-8')
    records.append({'sample': sample['name'], 'operation_ids': [operation.id for operation in order],
                    'measurement_counts': {operation_id: truth['count'] for operation_id, truth in expected},
                    'final_pixel_differences': 0, 'preview_pixel_differences': 0, 'measurement_parity': True})
report = {'zip_sha256': hashlib.sha256(package.read_bytes()).hexdigest(),
          'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
          'binary_bytes': binary.stat().st_size, 'selected_pipeline': request.selected_timeline_id,
          'exact_configuration': True, 'records': records}
(evidence / 'native-parity.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
