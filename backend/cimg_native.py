"""Use the same CImg core as the exported C++ program; no Python approximation."""
import ctypes as c
import sys
from functools import lru_cache
from pathlib import Path
import numpy as np

@lru_cache(maxsize=1)
def library():
    name='contour_cimg.dll' if sys.platform=='win32' else 'libcontour_cimg.dylib' if sys.platform=='darwin' else 'libcontour_cimg.so'
    path=Path(__file__).parent/'vendor/bin'/name
    if not path.exists():raise ValueError('CImg is not built yet. Run python scripts/build_vision.py, then retry this operation.')
    dll=c.CDLL(str(path));ptr=c.c_void_p
    dll.vision_cimg_distance.argtypes=[ptr,c.c_int,c.c_int,c.c_int64,c.c_int,ptr,ptr,c.c_uint32]
    dll.vision_cimg_distance.restype=c.c_int
    dll.vision_cimg_components.argtypes=[ptr,c.c_int,c.c_int,c.c_int64,c.c_int,c.c_uint32,c.c_uint32,c.c_int,ptr,ptr,ptr,c.c_uint32]
    dll.vision_cimg_components.restype=c.c_int
    return dll

def distance(image,params):
    image=np.ascontiguousarray(image);h,w=image.shape;out=np.empty((h,w),np.float32);error=c.create_string_buffer(512)
    result=library().vision_cimg_distance(image.ctypes.data,w,h,image.strides[0],{'chebyshev':0,'manhattan':1,'euclidean':2}[params['metric']],out.ctypes.data,error,len(error))
    if result<0:raise ValueError(error.value.decode('utf-8','replace'))
    return np.floor(np.clip(out.astype(np.float64)/params['pixels_per_level'],0,255)+.5).astype(np.uint8),float(out.max())

def components(image,params):
    image=np.ascontiguousarray(image);h,w=image.shape;out=np.empty_like(image);labels=np.empty((h,w),np.int32);error=c.create_string_buffer(512)
    count=library().vision_cimg_components(image.ctypes.data,w,h,image.strides[0],int(params['connectivity']),params['min_pixels'],params['max_pixels'],params['reject_border'],out.ctypes.data,labels.ctypes.data,error,len(error))
    if count<0:raise ValueError(error.value.decode('utf-8','replace'))
    if count>1000:raise ValueError('More than 1,000 connected regions. Increase minimum pixel area before measuring.')
    return out,labels,count
