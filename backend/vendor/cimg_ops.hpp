#pragma once
#define cimg_display 0
#define cimg_date "pinned-3.5.5"
#define cimg_time "reproducible"
// Do not define cimg_use_openmp: CImg 3.5.5 treats any definition as enabled.
#if defined(_OPENMP)
#error Compile this CPU-one-thread bridge without OpenMP
#endif
#include "CImg.h"
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <vector>

namespace vision_cimg {
using U8 = unsigned char;
using cimg_library::CImg;
inline std::size_t check(const U8* src,int w,int h,std::int64_t stride) {
    if(!src || w<=0 || h<=0 || w>4200000 || h>4200000 || std::int64_t(w)*h>4200000 || stride<w)
        throw std::invalid_argument("Invalid mask dimensions or stride");
    return std::size_t(w)*h;
}
inline CImg<U8> binary_copy(const U8* src,int w,int h,std::int64_t stride,int pad=0) {
    check(src,w,h,stride);
    CImg<U8> image(w+2*pad,h+2*pad,1,1,0);
    for(int y=0;y<h;++y)for(int x=0;x<w;++x)image(x+pad,y+pad)=src[y*stride+x]?255:0;
    return image;
}
// Distances are float pixels; outside the input is defined as background.
inline void distance(const U8* src,int w,int h,std::int64_t stride,int metric,float* out) {
    if(!out || metric<0 || metric>3)throw std::invalid_argument("Invalid distance output or metric");
    auto input=binary_copy(src,w,h,stride,1);
    auto d=input.get_distance(U8(0),static_cast<unsigned>(metric));
    for(int y=0;y<h;++y)for(int x=0;x<w;++x)out[std::size_t(y)*w+x]=d(x+1,y+1);
}
// Area filter uses actual foreground-pixel count; holes stay background.
// out_labels are contiguous int32 IDs 1..N for ACCEPTED components; zero is background.
// Input may alias out_mask because binary_copy happens before writing output.
inline int components(const U8* src,int w,int h,std::int64_t stride,int connectivity,
                      std::uint32_t min_pixels,std::uint32_t max_pixels,bool reject_border,
                      U8* out_mask,std::int32_t* out_labels) {
    const auto n=check(src,w,h,stride);
    if(!out_mask || !out_labels || (connectivity!=4 && connectivity!=8) || min_pixels>max_pixels)
        throw std::invalid_argument("Invalid connected-component parameters/output");
    auto input=binary_copy(src,w,h,stride);
    auto labels=input.get_label(connectivity==8,0,true);
    const auto size=static_cast<std::size_t>(labels.max())+1;
    std::vector<std::uint32_t> areas(size,0);
    std::vector<U8> border(size,0);
    for(int y=0;y<h;++y)for(int x=0;x<w;++x)if(input(x,y)) {
        const auto id=labels(x,y); ++areas[id];
        if(x==0 || y==0 || x==w-1 || y==h-1)border[id]=1;
    }
    std::vector<std::int32_t> canonical(size,0);
    int count=0;
    std::fill(out_mask,out_mask+n,0);std::fill(out_labels,out_labels+n,0);
    for(int y=0;y<h;++y)for(int x=0;x<w;++x)if(input(x,y)) {
        const auto id=labels(x,y);
        if(areas[id]>=min_pixels && areas[id]<=max_pixels && !(reject_border && border[id])) {
            if(!canonical[id])canonical[id]=++count;
            const auto p=std::size_t(y)*w+x;
            out_labels[p]=canonical[id];out_mask[p]=255;
        }
    }
    return count;
}
} // namespace vision_cimg
