#include "cimg_ops.hpp"
#include <cstdio>
#if defined(_WIN32)
#define VISION_API extern "C" __declspec(dllexport)
#else
#define VISION_API extern "C" __attribute__((visibility("default")))
#endif
inline int failure(char* error,std::uint32_t capacity,const char* message)noexcept {
    if(error && capacity)std::snprintf(error,capacity,"%s",message);return -1;
}
VISION_API int vision_cimg_version()noexcept{return cimg_version;}
VISION_API int vision_cimg_distance(const unsigned char* src,int w,int h,std::int64_t stride,int metric,
                                   float* output,char* error,std::uint32_t capacity)noexcept {
    try{vision_cimg::distance(src,w,h,stride,metric,output);return 0;}
    catch(const std::exception& e){return failure(error,capacity,e.what());}
    catch(...){return failure(error,capacity,"Unknown CImg distance error");}
}
VISION_API int vision_cimg_components(const unsigned char* src,int w,int h,std::int64_t stride,int connectivity,
                 std::uint32_t min_area,std::uint32_t max_area,int reject_border,unsigned char* mask,
                 std::int32_t* labels,char* error,std::uint32_t capacity)noexcept {
    try{return vision_cimg::components(src,w,h,stride,connectivity,min_area,max_area,reject_border!=0,mask,labels);}
    catch(const std::exception& e){return failure(error,capacity,e.what());}
    catch(...){return failure(error,capacity,"Unknown CImg components error");}
}
