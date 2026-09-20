"""Export a validated dependency closure with native detector geometry preserved."""
import io,json,zipfile
from collections import Counter
from pathlib import Path
from .timelines import resolve_paths,execution_plan,CATALOG,output_kind
from .vision_params import DETECTORS,supporting_ids
from .cpp_operations import operation_cpp

def validate_export_graph(request):
    resolved=resolve_paths(request.timelines)
    if request.selected_timeline_id not in resolved:raise ValueError('Select an existing pipeline.')
    order,previous,deps=execution_plan(request.timelines,request.selected_timeline_id,resolved)
    nodes={op.id:op for op in order};kinds={'source':'color'}
    for op in order:
        incoming=kinds[previous[op.id]]
        if incoming not in CATALOG[op.kind][1]:raise ValueError(f'Cannot export: {CATALOG[op.kind][0]} needs {" or ".join(CATALOG[op.kind][1])}, but receives {incoming}')
        outgoing=output_kind(op,incoming)
        if op.kind=='confirm':
            refs=supporting_ids(op)
            if nodes.get(previous[op.id]) is None or nodes[previous[op.id]].kind not in DETECTORS:raise ValueError('Cannot export: confirmation must immediately follow a detector')
            if len(refs)<op.params['min_support']:raise ValueError('Cannot export: choose enough supporting pipelines')
            if any(resolved[ref][-1].kind not in DETECTORS for ref in refs):raise ValueError('Cannot export: each supporting pipeline must finish with a detector')
        kinds[op.id]=outgoing
    return resolved,order,previous,kinds

def export_graph(request):
    resolved,order,previous,kinds=validate_export_graph(request);blocks=[];directory=Path(__file__).parent
    final=resolved[request.selected_timeline_id][-1].id
    dependencies=execution_plan(request.timelines,request.selected_timeline_id,resolved)[2]
    remaining=Counter(node for op in order for node in dependencies[op.id])
    has_cimg=any(op.kind.startswith('cimg_') for op in order);has_zxing=any(op.kind=='barcode' for op in order)
    boolstr=lambda v:str(v).lower();js=json.dumps
    for op in order:
        k,p=op.kind,op.params;id=js(op.id);prior=js(previous[op.id]);batch=None
        if k=='cimg_distance':code=f'next=distance_map(frame,{dict(chebyshev=0,manhattan=1,euclidean=2)[p["metric"]]},{p["pixels_per_level"]});'
        elif k=='cimg_components':batch=f'components(frame,source,{p["connectivity"]},{p["min_pixels"]},{p["max_pixels"]},{boolstr(p["reject_border"])})'
        elif k=='hough_circles':batch=f'circles(frame,source,{p["min_distance"]},{p["edge_threshold"]},{p["votes"]},{p["min_radius"]},{p["max_radius"]})'
        elif k=='hough_lines':batch=f'segments(frame,source,{p["votes"]},{p["min_length"]},{p["max_gap"]})'
        elif k=='barcode':
            format={'all':'None','qr':'QRCode','linear':'LinearCodes','data_matrix':'DataMatrix'}[p['formats']];binarizer={'local_average':'LocalAverage','global_histogram':'GlobalHistogram','fixed_threshold':'FixedThreshold'}[p['binarizer']]
            batch=f'barcodes(frame,source,ZXing::BarcodeFormat::{format},{boolstr(p["try_rotate"])},{boolstr(p["try_downscale"])},ZXing::Binarizer::{binarizer})'
        elif k=='confirm':
            supports=','.join(f'&batches.at({js(resolved[tid][-1].id)})' for tid in supporting_ids(op))
            batch=f'confirm(batches.at({prior}),std::vector<const Batch*>{{{supports}}},{p["min_support"]},{p["iou"]},{boolstr(p["match_text"])})'
        elif k=='contours':
            values=','.join(boolstr(p[key]) for key in ('min_area','max_area','min_circularity','min_solidity','min_aspect','max_aspect','reject_border'))
            batch=f'contours(frame,source,Filter{{{values}}})'
        else:code=operation_cpp(op,kinds[previous[op.id]])
        if batch:code=f'batches[{id}]={batch};render(batches.at({id}),source,next,preview);'
        guard='' if k=='resize' else 'if(frame.total()>4200000)throw std::runtime_error("Add Resize first for images over 4.2 megapixels");'
        save_preview=f'final_preview=preview;' if op.id==final else ''
        save_measurement=f'measurements.push_back(batch_json(batches.at({id}),source,{id}));' if batch else ''
        release=[]
        for dependency in dependencies[op.id]:
            remaining[dependency]-=1
            if remaining[dependency]==0 and dependency not in ('source',final):
                release.append(f'frames.erase({js(dependency)});batches.erase({js(dependency)});')
        blocks.append(f'{{auto begin=std::chrono::steady_clock::now();cv::Mat frame=frames.at({prior}),next,preview;'+guard+code+f'frames[{id}]=next;{save_preview}steps.push_back(Step{{{id},{js(k)},elapsed(begin)}});'+save_measurement+''.join(release)+'}')
    m=request.measurements;constants=[f'constexpr double pixels_per_unit={m.pixels_per_unit};',f'constexpr const char* unit={js(m.unit if m.pixels_per_unit else "px")};']+[f'constexpr bool measure_{field}={boolstr(field in m.fields)};' for field in ['length','width','area','angle','color','center']]
    header=(directory/'detector.cpp.in').read_text(encoding='utf-8').split('struct Detection {')[0].replace('// GENERATED_CONSTANTS','\n'.join(constants))
    main=(directory/'timeline.cpp.in').read_text(encoding='utf-8').split('int main(',1)[1]
    source=('#define CONTOUR_CIMG\n' if has_cimg else '')+('#define CONTOUR_ZXING\n' if has_zxing else '')+header+(directory/'native_vision.cpp.in').read_text(encoding='utf-8')
    source=source.replace('// GENERATED_OPERATIONS','\n'.join(blocks)).replace('// GENERATED_MAIN','int main('+main).replace('GENERATED_FINAL_KIND',kinds[final]).replace('GENERATED_FINAL_ID',final)
    standard=20 if has_zxing else 17
    cmake=f'''cmake_minimum_required(VERSION 3.16)
project(contour_detector LANGUAGES CXX)
find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs)
add_executable(detector detector.cpp)
target_compile_features(detector PRIVATE cxx_std_{standard})
target_include_directories(detector PRIVATE ${{OpenCV_INCLUDE_DIRS}})
target_link_libraries(detector PRIVATE ${{OpenCV_LIBS}})
'''
    if has_zxing:cmake+='''set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(ZXING_READERS ON CACHE BOOL "" FORCE)
set(ZXING_WRITERS OFF CACHE BOOL "" FORCE)
set(ZXING_EXAMPLES OFF CACHE BOOL "" FORCE)
set(ZXING_UNIT_TESTS OFF CACHE BOOL "" FORCE)
add_subdirectory(vendor/zxing EXCLUDE_FROM_ALL)
target_link_libraries(detector PRIVATE ZXing::ZXing)
'''
    libraries=['OpenCV core/imgproc/imgcodecs']+(['CImg 3.5.5 (included header)'] if has_cimg else [])+(['ZXing-C++ 2.3.0 (included sources)'] if has_zxing else [])
    readme=f'''# Exported CPU vision pipeline

This C++{standard} program executes the selected pipeline and all supporting branches in
dependency order. Shared operations run once. Libraries: {', '.join(libraries)}.
Only OpenCV, CMake and a C++{standard} compiler must be installed. Included library sources
and licenses are under vendor/. No Python, model, GPU, API key or network is used at runtime
or required to download dependencies during this build. Compile without OpenMP.

    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build --config Release
    ./build/detector --output final.png --preview overlay.png image.png

Windows multi-config builds use build/Release/detector.exe. Set -DOpenCV_DIR=... when needed.
JSON includes each executed step's latency and every required detector's results. The
selected final detector is {final}; supporting outputs are not additional final detections.
config.json describes compiled constants; changing it does not modify the executable.

Measurements are in original image coordinates and the configured physical scale. Components
use axis-aligned extents and foreground-pixel area (holes excluded). Contours use rotated
rectangles and filled external-contour area (holes included). Circles describe the fitted
disk; lines report endpoint distance, null width/area, and original pixel endpoints. Barcodes
report decoded text, format and code quadrilateral dimensions. Code text is data, never executed.
Mean RGB samples original-source pixels in each detector's region. Confirmation preserves
primary measurements/membership and uses deterministic one-to-one box overlap with each
support; agreement is not a probability of correctness. Different resolutions match through
normalized coordinates. Geometry and fitted extents must be checked on representative images.

One CPU thread, OpenCL off. Timings are single native runs, not builder medians or target
estimates. Benchmark on the target. OpenCV version/build changes can alter edge pixels.
8-bit PNG/JPEG/WebP inputs, maximum 24MP; add Resize before operations above 4.2MP.
Physical dimensions require a valid scale in the object's plane. Decoder EXIF behavior may
differ across builds; validate the exported program with the images used for deployment.
'''
    config={'selected_timeline_id':request.selected_timeline_id,'selected_path':[op.id for op in resolved[request.selected_timeline_id]],'operations':[op.model_dump() for op in order],'pipelines':[t.model_dump() for t in request.timelines if any(op.id in {o.id for o in order} for op in t.operations)],'measurements':m.model_dump(),'libraries':libraries,'cpp_standard':standard}
    result=io.BytesIO()
    with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,text in {'detector.cpp':source,'CMakeLists.txt':cmake,'README.md':readme,'config.json':json.dumps(config,indent=2)}.items():archive.writestr(name,text)
        if has_cimg:
            for name in ['CImg.h','cimg_ops.hpp','CImg-LICENSE.txt']:archive.write(directory/'vendor'/name,'vendor/'+name)
        if has_zxing:
            with zipfile.ZipFile(directory/'vendor/zxing-2.3.0.zip') as dependency:
                for info in dependency.infolist():
                    path=Path(info.filename);parts=path.parts[1:]
                    if info.is_dir() or not parts or '..' in parts:continue
                    archive.writestr('vendor/zxing/'+'/'.join(parts),dependency.read(info))
    return result.getvalue()
