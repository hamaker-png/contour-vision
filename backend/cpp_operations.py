"""Allowlisted straight-line OpenCV operation snippets."""
import json
import numpy as np

def operation_cpp(op,incoming):
    from .standard_ops import STANDARD_CATALOG,standard_cpp
    if op.kind in STANDARD_CATALOG:return standard_cpp(op.kind,op.params)
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
    return code
