"""Reproduce the 90-image Python/C++ decoder matrix from the repository root.

Requires the project's Python dependencies (including Pillow with WebP support),
CMake, a C++17 compiler, and OpenCV core/imgproc/imgcodecs development libraries.
No internet images or prior benchmark artifacts are needed. Three fixed graphs
are exported and compiled: identity color, threshold/components, and gray/gamma.

    python scripts/check_native_image_loading.py
    python scripts/check_native_image_loading.py --opencv-dir /path/to/opencv/lib/cmake/opencv4
    python scripts/check_native_image_loading.py --output /tmp/loader-check --system-toolchain

The existing Windows .tools compiler wrappers and .venv CMake/Ninja are used
when present; --system-toolchain uses the normal CMake compiler discovery.
Additional CMake options: --cmake-arg=-DCMAKE_CXX_COMPILER=/path/to/compiler
Existing exports may be reused with --skip-build; each must contain config.json,
detector.cpp, and build/detector (or build/Release/detector.exe). An optional
--existing-gray-gamma directory supplies the third export without rebuilding it.
The script rejects stale loader source in any supplied export. Binary/source
hashes and exact build commands are recorded; skip-build alone does not prove
that a supplied binary was compiled from its adjacent source.

Output includes source fixtures, manifests, native images, report.json, exported
packages and build logs. A previous report is backed up before replacement.
These analytic metadata/alpha fixtures test decoder parity, not natural-image
detection reliability. Malformed metadata fuzzing is outside this matrix.
"""

import argparse
import base64
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile

import cv2
import numpy as np
from PIL import Image, features

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.engine import decode_image
from backend.models import Measurements
from backend.search_execution import execute
from backend.timeline_exporter import TimelineExportRequest, export_timeline
from backend.timelines import Timeline


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def loader_source(text):
    """Exclude generated measurement constants and graph implementation."""
    start = text.index('// Read only the bounded IFD0 orientation tag.')
    end = text.index('    return result;\n}', start) + len('    return result;\n}')
    return text[start:end]


def binary_path(directory):
    for name in ['build/detector', 'build/detector.exe', 'build/Release/detector.exe']:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f'No compiled detector in {directory}/build')


def fixed_graphs():
    def graph(name, operations):
        return [Timeline.model_validate(dict(id='main', name=name, operations=operations))]
    return {
        'identity_color': graph('Unmodified decoded color', [dict(id='identity', kind='gamma', params={'gamma': 1})]),
        'holed_parts': graph('Component measurement', [
            dict(id='grayscale', kind='grayscale', params={}),
            dict(id='threshold', kind='threshold', params={'value': 142}),
            dict(id='cimg_components', kind='cimg_components', params={
                'connectivity': '8', 'min_pixels': 30, 'max_pixels': 4200000, 'reject_border': True}),
        ]),
        'gray_gamma': graph('Grayscale gamma .7', [
            dict(id='grayscale', kind='grayscale', params={}),
            dict(id='gamma', kind='gamma', params={'gamma': .7}),
        ]),
    }


def build_program(label, graphs, directory, args, native_root):
    directory.mkdir(parents=True, exist_ok=True)
    measurement = Measurements(fields=['length', 'width', 'area', 'angle', 'center', 'color'])
    package = export_timeline(TimelineExportRequest(
        timelines=graphs, selected_timeline_id='main', measurements=measurement))
    (directory / 'download.zip').write_bytes(package)
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            destination = (directory / info.filename).resolve()
            if directory.resolve() not in destination.parents:
                raise ValueError('Unexpected export archive path')
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(info))
    bundled_cmake = ROOT / '.venv/Lib/site-packages/cmake/data/bin/cmake.exe'
    cmake = args.cmake or (str(bundled_cmake) if bundled_cmake.exists() else shutil.which('cmake'))
    if not cmake:
        raise RuntimeError('CMake is required; install it or pass --cmake')
    command = [cmake, '-S', str(directory), '-B', str(directory / 'build'), '-DCMAKE_BUILD_TYPE=Release']
    bundled_ninja = ROOT / '.venv/Scripts/ninja.exe'
    ninja = str(bundled_ninja) if bundled_ninja.exists() else shutil.which('ninja')
    if ninja:
        command += ['-G', 'Ninja', f'-DCMAKE_MAKE_PROGRAM={Path(ninja).as_posix()}']
    if not args.system_toolchain and (ROOT / '.tools/cxx.cmd').exists():
        for option, file in [('CMAKE_CXX_COMPILER', 'cxx.cmd'), ('CMAKE_C_COMPILER', 'cc.cmd'),
                             ('CMAKE_AR', 'ar.cmd'), ('CMAKE_RANLIB', 'ranlib.cmd')]:
            command.append(f'-D{option}={(ROOT / ".tools" / file).as_posix()}')
    opencv = args.opencv_dir
    if opencv is None and not args.system_toolchain and (ROOT / '.tools/opencv-build').is_dir():
        opencv = ROOT / '.tools/opencv-build'
    if opencv is not None:
        command.append(f'-DOpenCV_DIR={opencv.resolve().as_posix()}')
    command += args.cmake_arg
    build = [cmake, '--build', str(directory / 'build'), '--config', 'Release', '--parallel', str(args.parallel)]
    env = os.environ.copy()
    env['ZIG_GLOBAL_CACHE_DIR'] = str(native_root / 'zig-cache')
    env['ZIG_LOCAL_CACHE_DIR'] = str(native_root / 'zig-local-cache')
    print(f'Compiling {label}', flush=True)
    for step, invocation in [('configure', command), ('build', build)]:
        result = subprocess.run(invocation, env=env, text=True, capture_output=True)
        (directory / f'{step}.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(f'{label} {step} failed; see {directory / (step + ".log")}')
    return {'configure_command': command, 'build_command': build, 'export_sha256': sha(package)}


def make_fixtures(directory):
    directory.mkdir(parents=True, exist_ok=True)
    rgb = np.full((96, 144, 3), 30, np.uint8)
    rgb[10:40, 15:65] = (20, 210, 240)
    rgb[60:85, 95:128] = (220, 240, 30)
    rgb[50:57, 35:80] = (80, 90, 100)
    color = Image.fromarray(rgb)
    gray = color.convert('L')
    alpha = np.full((96, 144), 255, np.uint8)
    alpha[10:40, 15:65] = 128
    alpha[60:85, 95:128] = np.linspace(0, 255, 33, dtype=np.uint8)[None, :]
    transparent = Image.fromarray(np.dstack([rgb, alpha]))
    grayalpha = Image.merge('LA', (gray, Image.fromarray(alpha)))
    cases = []

    def save(name, image, format='PNG', orientation=None, endian=None, **options):
        extension = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}[format]
        path = directory / (name + '.' + extension)
        image.save(path, format=format, **options)
        with Image.open(path) as check:
            read_orientation = check.getexif().get(274, 1)
        if orientation is not None and read_orientation != orientation:
            raise ValueError(f'Fixture metadata readback failed for {name}')
        cases.append(dict(name=name, path=str(path), mime={'PNG': 'png', 'JPEG': 'jpeg', 'WEBP': 'webp'}[format],
                          source_mode=image.mode, sha256=sha(path.read_bytes()), declared_orientation=orientation,
                          endian=endian, read_back_orientation=read_orientation))

    save('rgb_png', color)
    save('partial_alpha_png', transparent)
    save('grayscale_png', gray)
    save('gray_alpha_png', grayalpha)
    palette = color.quantize(colors=16)
    palette.info['transparency'] = bytes([0, 32, 64, 128, 192, 255] + [255] * 250)
    save('palette_partial_alpha_png', palette)
    save('rgb_jpeg', color, 'JPEG', quality=95, subsampling=0)
    save('rgb_webp_lossless', color, 'WEBP', lossless=True)
    save('rgba_webp_lossless', transparent, 'WEBP', lossless=True)
    save('rgb_webp_lossy', color, 'WEBP', quality=80)
    for endian in ['little', 'big']:
        order = '<' if endian == 'little' else '>'
        prefix = b'II' if endian == 'little' else b'MM'
        for orientation in range(1, 9):
            exif = (b'Exif\x00\x00' + prefix + struct.pack(order + 'HIH', 42, 8, 1)
                    + struct.pack(order + 'HHIHHI', 274, 3, 1, orientation, 0, 0))
            for label, image, format, options in [
                ('rgb_jpeg', color, 'JPEG', dict(quality=95, subsampling=0)),
                ('gray_jpeg', gray, 'JPEG', dict(quality=95)),
                ('rgba_png', transparent, 'PNG', {}),
                ('rgb_webp', color, 'WEBP', dict(lossless=True)),
                ('rgba_webp', transparent, 'WEBP', dict(lossless=True)),
            ]:
                save(f'{label}_exif_{endian}_{orientation}', image, format, orientation=orientation,
                     endian=endian, exif=exif, **options)
    save('png_16bit_guard', Image.fromarray(np.array(gray).astype(np.uint16) * 257))
    return cases


def compare(label, directory, cases, output, expected_loader):
    source = (directory / 'detector.cpp').read_text(encoding='utf-8')
    if loader_source(source) != expected_loader:
        raise RuntimeError(f'{label} has stale loader source; rebuild its export')
    binary = binary_path(directory)
    binary_hash = sha(binary.read_bytes())
    config = json.loads((directory / 'config.json').read_text(encoding='utf-8'))
    graphs = [Timeline.model_validate(t) for t in config['pipelines']]
    measurement = Measurements.model_validate(config['measurements'])
    records = []
    for case in cases:
        path = Path(case['path'])
        data = 'data:image/' + case['mime'] + ';base64,' + base64.b64encode(path.read_bytes()).decode()
        python_error = None
        try:
            image = decode_image(data)
            frame, _ = execute(image, graphs, config['selected_timeline_id'], measurement)
        except ValueError as error:
            python_error = str(error)
        target = output / (case['name'] + '-' + label + '-native.png')
        native = subprocess.run([str(binary), '--output', str(target), str(path)],
                                text=True, capture_output=True, timeout=15)
        row = dict(binary=label, binary_sha256=binary_hash, case=case['name'], python_error=python_error,
                   native_exit=native.returncode, native_error=native.stderr.strip(), source_sha256=case['sha256'])
        if python_error or native.returncode:
            row['both_rejected'] = bool(python_error and native.returncode)
            row['passed'] = row['both_rejected'] and case['name'] == 'png_16bit_guard'
        else:
            payload = json.loads(native.stdout)
            actual = cv2.imread(str(target), cv2.IMREAD_UNCHANGED)
            if actual is None:
                raise RuntimeError(f'Missing native output: {target}')
            row.update(python_shape=list(frame.image.shape), native_shape=list(actual.shape),
                       shape_equal=frame.image.shape == actual.shape)
            delta = abs(actual.astype(np.int16) - frame.image.astype(np.int16)) if row['shape_equal'] else None
            row['pixel_differences'] = int(np.count_nonzero(delta)) if delta is not None else None
            row['max_pixel_difference'] = int(delta.max()) if delta is not None else None
            steps = payload['measurement_steps']
            native_detections = steps[-1]['detections'] if steps else []
            python_detections = frame.details.get('detections', [])
            row.update(python_count=len(python_detections), native_count=len(native_detections))
            row['box_and_measurements_equal'] = len(native_detections) == len(python_detections) and all(
                a['box'] == b['box'] and a['measurements'] == b['measurements']
                for a, b in zip(native_detections, python_detections))
            if not row['box_and_measurements_equal']:
                row.update(python_detections=python_detections, native_detections=native_detections)
            row['passed'] = row['shape_equal'] and row['pixel_differences'] == 0 and row['box_and_measurements_equal']
        records.append(row)
        if not row['passed']:
            print(json.dumps(row), flush=True)
    print(f'{label}: {sum(r["passed"] for r in records)}/{len(records)} passed', flush=True)
    return records, dict(source_sha256=sha(source.encode()), binary_sha256=binary_hash,
                        binary_bytes=binary.stat().st_size, loader_matches_current_template=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/native-image-loading')
    parser.add_argument('--native-dir', type=Path, help='Export/build directory (default: OUTPUT/native)')
    parser.add_argument('--existing-gray-gamma', type=Path, help='Use this third export without rebuilding it')
    parser.add_argument('--skip-build', action='store_true')
    parser.add_argument('--system-toolchain', action='store_true')
    parser.add_argument('--opencv-dir', type=Path)
    parser.add_argument('--cmake')
    parser.add_argument('--cmake-arg', action='append', default=[])
    parser.add_argument('--parallel', type=int, default=2)
    args = parser.parse_args()
    if args.parallel < 1:
        parser.error('--parallel must be positive')
    if not features.check('webp'):
        parser.error('Pillow with WebP support is required')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    native_root = (args.native_dir or output / 'native').resolve()
    native_root.mkdir(parents=True, exist_ok=True)
    expected_loader = loader_source((ROOT / 'backend/detector.cpp.in').read_text(encoding='utf-8'))
    programs = {name: native_root / name for name in fixed_graphs()}
    build_info = {}
    for label, graphs in fixed_graphs().items():
        if label == 'gray_gamma' and args.existing_gray_gamma:
            programs[label] = args.existing_gray_gamma.resolve()
        elif not args.skip_build:
            build_info[label] = build_program(label, graphs, programs[label], args, native_root)
    cases = make_fixtures(output)
    manifest = dict(recorded_utc=now(), scope='Synthetic decoder fixtures: 80 valid orientations, 9 plain/alpha images, one 16-bit guard.', cases=cases)
    report = dict(recorded_utc=now(), python_opencv=cv2.__version__, loader_sha256=sha(expected_loader.encode()),
                  script_sha256=sha(Path(__file__).read_bytes()), skip_build=args.skip_build,
                  scope='90-image decoder parity, not detection generalization or malformed metadata fuzzing.',
                  programs={}, records=[])
    for label, directory in programs.items():
        records, provenance = compare(label, directory, cases, output, expected_loader)
        report['records'].extend(records)
        report['programs'][label] = {**build_info.get(label, {}), **provenance, 'directory': str(directory)}
    report['summary'] = {label: dict(
        cases=sum(r['binary'] == label for r in report['records']),
        passed=sum(r['binary'] == label and r['passed'] for r in report['records']),
        failed=[r['case'] for r in report['records'] if r['binary'] == label and not r['passed']],
        measured_objects=sum(r.get('python_count', 0) for r in report['records'] if r['binary'] == label),
    ) for label in programs}
    current_loader = loader_source((ROOT / 'backend/detector.cpp.in').read_text(encoding='utf-8'))
    report['template_unchanged_during_run'] = current_loader == expected_loader
    for name, value in [('input-manifest.json', manifest), ('report.json', report)]:
        destination = output / name
        if destination.exists():
            stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            shutil.copy2(destination, output / f'{destination.stem}-previous-{stamp}.json')
        destination.write_text(json.dumps(value, indent=2), encoding='utf-8')
    print(json.dumps(report['summary'], indent=2))
    return 0 if report['template_unchanged_during_run'] and all(r['passed'] for r in report['records']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
