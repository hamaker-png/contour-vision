"""Compile a validated human-selected transform path to straight-line C++17."""
import io
import json
from pathlib import Path
import zipfile

import numpy as np
from pydantic import Field, model_validator

from .models import Measurements, StrictModel
from .timelines import Timeline, resolve_paths, path_kinds


class TimelineExportRequest(StrictModel):
    timelines: list[Timeline] = Field(min_length=1,max_length=8)
    selected_timeline_id: str
    measurements: Measurements = Field(default_factory=Measurements)

    @model_validator(mode='after')
    def valid(self):
        paths=resolve_paths(self.timelines)
        if self.selected_timeline_id not in paths:raise ValueError('Select an existing pipeline to export')
        from .graph_exporter import validate_export_graph
        validate_export_graph(self)
        return self


def validate_path(operations):
    return path_kinds(operations,'Cannot export')


def export_timeline(request):
    from .timelines import execution_plan
    from .vision_params import EXTRA_CATALOG
    if any(op.kind in EXTRA_CATALOG for op in execution_plan(request.timelines,request.selected_timeline_id)[0]):
        from .graph_exporter import export_graph
        return export_graph(request)
    operations=resolve_paths(request.timelines)[request.selected_timeline_id]
    kinds=validate_path(operations);blocks=[]
    for op,(incoming,outgoing) in zip(operations,kinds):
        p=op.params;k=op.kind;code=''
        if k=='resize':
            interp='cv::INTER_NEAREST' if incoming=='mask' else 'cv::INTER_AREA'
            code=f'double s=std::min(1.0,{p["max_side"]}.0/std::max(frame.cols,frame.rows)); cv::resize(frame,next,cv::Size(std::max(1,int(std::lround(frame.cols*s))),std::max(1,int(std::lround(frame.rows*s)))),0,0,{interp});'
        elif k=='gaussian_blur':code=f'cv::GaussianBlur(frame,next,cv::Size({p["kernel"]},{p["kernel"]}),0);'
        elif k=='median_blur':code=f'cv::medianBlur(frame,next,{p["kernel"]});' if p['kernel']>1 else 'next=frame.clone();'
        elif k=='grayscale':code='cv::cvtColor(frame,next,cv::COLOR_BGR2GRAY);'
        elif k=='channel':
            channel=p['channel'];index={'blue':0,'green':1,'red':2,'hue':0,'saturation':1,'value':2}[channel]
            code=f'cv::extractChannel(frame,next,{index});' if channel in ('red','green','blue') else f'cv::Mat hsv;cv::cvtColor(frame,hsv,cv::COLOR_BGR2HSV);cv::extractChannel(hsv,next,{index});'
            if channel=='hue':
                lut=np.round(np.arange(180,dtype=np.float32)*255/179).astype(np.uint8).tolist()
                code+=' const unsigned char hue_lut[180]={'+','.join(map(str,lut))+'}; for(int y=0;y<next.rows;++y)for(int x=0;x<next.cols;++x)next.at<unsigned char>(y,x)=hue_lut[next.at<unsigned char>(y,x)];'
        elif k=='hsv_mask':
            code=f'cv::Mat hsv;cv::cvtColor(frame,hsv,cv::COLOR_BGR2HSV);auto band=[&](int lo,int hi){{cv::Mat m;cv::inRange(hsv,cv::Scalar(lo,{p["saturation_low"]},{p["value_low"]}),cv::Scalar(hi,{p["saturation_high"]},{p["value_high"]}),m);return m;}};'
            code+=f'next=band({p["hue_low"]},{p["hue_high"]});' if p['hue_low']<=p['hue_high'] else f'cv::bitwise_or(band({p["hue_low"]},179),band(0,{p["hue_high"]}),next);'
        elif k=='clahe':code=f'cv::createCLAHE({p["clip_limit"]},cv::Size({p["tile_size"]},{p["tile_size"]}))->apply(frame,next);'
        elif k in ('otsu','threshold'):code=f'cv::threshold(frame,next,{p.get("value",0)},255,cv::THRESH_BINARY'+('|cv::THRESH_OTSU' if k=='otsu' else '')+');'
        elif k=='adaptive_threshold':code=f'cv::adaptiveThreshold(frame,next,255,cv::ADAPTIVE_THRESH_GAUSSIAN_C,cv::THRESH_BINARY,{p["block_size"]},{p["constant"]});'
        elif k=='canny':code=f'cv::Canny(frame,next,{p["low"]},{p["high"]});'
        elif k=='invert':code='cv::bitwise_not(frame,next);'
        elif k in ('morph_open','morph_close','erode','dilate'):
            mode={'morph_open':'MORPH_OPEN','morph_close':'MORPH_CLOSE','erode':'MORPH_ERODE','dilate':'MORPH_DILATE'}[k]
            code=f'cv::morphologyEx(frame,next,cv::{mode},cv::getStructuringElement(cv::MORPH_ELLIPSE,cv::Size({p["kernel"]},{p["kernel"]})));'
        elif k=='contours':
            fields=['min_area','max_area','min_circularity','min_solidity','min_aspect','max_aspect','reject_border']
            args=','.join(str(p[f]).lower() for f in fields)
            code=f'measurements.push_back(measure(frame,source,next,preview,Filter{{{args}}},{json.dumps(op.id)}));'
        guard='' if k=='resize' else 'if(frame.total()>4200000)throw std::runtime_error("Add Resize first for images over 4.2 megapixels");'
        blocks.append('{ auto begin=std::chrono::steady_clock::now();cv::Mat next;preview.release();'+guard+code+
                      f' frame=next;steps.push_back(Step{{{json.dumps(op.id)},{json.dumps(k)},elapsed(begin)}}); }}')
    m=request.measurements
    constants=[f'constexpr double pixels_per_unit={m.pixels_per_unit};',f'constexpr const char* unit={json.dumps(m.unit if m.pixels_per_unit else "px")};']
    constants += [f'constexpr bool measure_{f}={str(f in m.fields).lower()};' for f in ['length','width','area','angle','color','center']]
    directory=Path(__file__).parent
    header=(directory/'detector.cpp.in').read_text(encoding='utf-8').split('struct Detection {')[0].replace('// GENERATED_CONSTANTS','\n'.join(constants))
    source=header+(directory/'timeline.cpp.in').read_text(encoding='utf-8')
    source=source.replace('// GENERATED_OPERATIONS','\n'.join(blocks)).replace('GENERATED_FINAL_KIND',kinds[-1][1] if kinds else 'color')
    cmake='''cmake_minimum_required(VERSION 3.16)
project(timeline_detector LANGUAGES CXX)
find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs)
add_executable(detector detector.cpp)
target_compile_features(detector PRIVATE cxx_std_17)
target_include_directories(detector PRIVATE ${OpenCV_INCLUDE_DIRS})
target_link_libraries(detector PRIVATE ${OpenCV_LIBS})
'''
    readme='''# Exported CPU vision pipeline

The selected path is flattened through its shared parent prefix and compiled in the exact
edited order. This C++17 program needs OpenCV core/imgproc/imgcodecs, a compiler and CMake.
It runs on one CPU thread with OpenCL disabled. No Python, GPU, model, API key or network is used.

    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build --config Release
    ./build/detector image.png
    ./build/detector --output final.png --preview overlay.png image.png
    ./build/detector image1.png image2.jpg

Windows multi-config builds use build/Release/detector.exe. Set -DOpenCV_DIR=... if needed.
Each input yields one JSON line: final output kind/dimensions, actual per-operation CPU
latencies, total processing latency, and every measurement step's detections. --output saves
the actual final transform pixels; --preview saves the final contour overlay if available.
Output-file options accept one input only. Errors go to stderr with a nonzero exit status.

Inputs: ordinary 8-bit PNG/JPEG/WebP, transparency composited over white, max 24 megapixels.
Steps above 4.2MP require Resize first. Length/width are rotated rectangle sides; area is filled
external contour area (holes included); mean RGB comes from the ORIGINAL source resized
directly to the measurement resolution. Center/boxes remain in original pixels. Near-square
objects have null angle. Positive pixels_per_unit calibrates lengths and squared areas;
perspective or changing camera/plane invalidates that calibration.

These constants are compiled into detector.cpp. config.json is descriptive, not loaded at
runtime. Re-export/rebuild after editing the workspace. Binary timings are single runs on
the executing CPU, not the UI's five-run medians or target estimates. Benchmark repeatedly
on your deployment device. Different OpenCV versions/build flags can change edge pixels;
verify exported output on your own images. Detector accuracy is limited to tested conditions.
'''
    config={'selected_timeline_id':request.selected_timeline_id,'operations':[o.model_dump() for o in operations], 'measurements':m.model_dump()}
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,text in {'detector.cpp':source,'CMakeLists.txt':cmake,'README.md':readme,'config.json':json.dumps(config,indent=2)}.items():archive.writestr(name,text)
    return buffer.getvalue()
