"""Bounded classical image operations with identical preview/export semantics."""
from typing import Literal
import cv2
import numpy as np
from pydantic import Field, model_validator
from .models import StrictModel

class NoParams(StrictModel):
    pass

class MorphParams(StrictModel):
    kernel: int = Field(default=15, ge=1, le=63)
    @model_validator(mode='after')
    def odd(self):
        if self.kernel % 2 == 0: raise ValueError('Kernel size must be odd')
        return self

class GradientParams(StrictModel):
    direction: Literal['magnitude','x','y'] = 'magnitude'
    kernel: int = Field(default=3, ge=3, le=7)
    gain: float = Field(default=.25, ge=.001, le=4)
    @model_validator(mode='after')
    def odd(self):
        if self.kernel % 2 == 0: raise ValueError('Sobel kernel must be 3, 5 or 7')
        return self

class RangeParams(StrictModel):
    low: int = Field(default=0, ge=0, le=255)
    high: int = Field(default=127, ge=0, le=255)
    @model_validator(mode='after')
    def ordered(self):
        if self.low > self.high: raise ValueError('Intensity low must not exceed high')
        return self

class GammaParams(StrictModel):
    gamma: float = Field(default=1, ge=.1, le=5)

STANDARD_CATALOG = {
    'fill_holes':('Fill enclosed holes',['mask'],'Fill all background holes with no 4-connected path to outside the image. Changes object area; open gaps remain open.',NoParams),
    'top_hat':('Bright detail · top-hat',['gray'],'Subtract a morphological opening to isolate bright details smaller than the kernel under uneven illumination.',MorphParams),
    'black_hat':('Dark detail · black-hat',['gray'],'Subtract the image from a morphological closing to reveal dark details smaller than the kernel.',MorphParams),
    'sobel':('Sobel gradient',['gray','mask'],'Signed derivatives followed by absolute X/Y or magnitude. Fixed gain, clipped to 0–255; no image-dependent normalization.',GradientParams),
    'range_mask':('Intensity range mask',['gray','mask'],'Select intensities inside an inclusive low/high range. Useful for dark or mid-tone objects without a separate inversion.',RangeParams),
    'morph_gradient':('Morphological gradient',['gray','mask'],'Dilation minus erosion with an elliptical kernel. Reveals local boundaries; a binary input stays binary.',MorphParams),
    'gamma':('Gamma correction',['color','gray'],'Fixed lookup: round(255 × (intensity / 255)^gamma). Below 1 brightens; above 1 darkens. Color is changed in the working image only.',GammaParams),
}

def gamma_table(value):
    return np.floor(255*(np.arange(256,dtype=np.float64)/255)**value+.5).astype(np.uint8)

def apply_standard(image, kind, params):
    if kind=='gamma': return cv2.LUT(image,gamma_table(params['gamma']))
    if kind=='range_mask': return cv2.inRange(image,params['low'],params['high'])
    if kind=='fill_holes':
        padded=cv2.copyMakeBorder(image,1,1,1,1,cv2.BORDER_CONSTANT,value=0)
        cv2.floodFill(padded,None,(0,0),255,flags=4)
        return cv2.bitwise_or(image,cv2.bitwise_not(padded[1:-1,1:-1]))
    if kind=='sobel':
        k,g=params['kernel'],params['gain']
        if params['direction'] in ('x','y'):
            dx=int(params['direction']=='x')
            derivative=np.abs(cv2.Sobel(image,cv2.CV_64F,dx,1-dx,ksize=k))
        else:
            x=cv2.Sobel(image,cv2.CV_64F,1,0,ksize=k)
            y=cv2.Sobel(image,cv2.CV_64F,0,1,ksize=k)
            # OpenCV's float magnitude approximation varies across versions/CPUs.
            # Double precision and explicit half-up rounding preserve export masks.
            derivative=np.sqrt(x*x+y*y)
        return np.floor(np.minimum(derivative*g,255)+.5).astype(np.uint8)
    mode={'top_hat':cv2.MORPH_TOPHAT,'black_hat':cv2.MORPH_BLACKHAT,'morph_gradient':cv2.MORPH_GRADIENT}[kind]
    return cv2.morphologyEx(image,mode,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(params['kernel'],params['kernel'])))

def standard_cpp(kind,params):
    if kind=='gamma':
        values=','.join(map(str,gamma_table(params['gamma']).tolist()))
        return f'const unsigned char values[256]={{{values}}};cv::Mat lut(1,256,CV_8U,const_cast<unsigned char*>(values));cv::LUT(frame,lut,next);'
    if kind=='range_mask':return f'cv::inRange(frame,cv::Scalar({params["low"]}),cv::Scalar({params["high"]}),next);'
    if kind=='fill_holes':return 'cv::Mat padded;cv::copyMakeBorder(frame,padded,1,1,1,1,cv::BORDER_CONSTANT,cv::Scalar(0));cv::floodFill(padded,cv::Point(0,0),cv::Scalar(255),nullptr,cv::Scalar(),cv::Scalar(),4);cv::Mat holes;cv::bitwise_not(padded(cv::Rect(1,1,frame.cols,frame.rows)),holes);cv::bitwise_or(frame,holes,next);'
    if kind=='sobel':
        k=params['kernel'];g=params['gain']
        if params['direction'] in ('x','y'):
            dx=int(params['direction']=='x')
            setup=f'cv::Mat x;cv::Sobel(frame,x,CV_64F,{dx},{1-dx},{k});'
            value='std::abs(x.at<double>(r,c))'
        else:
            setup=f'cv::Mat x,y;cv::Sobel(frame,x,CV_64F,1,0,{k});cv::Sobel(frame,y,CV_64F,0,1,{k});'
            value='std::sqrt(x.at<double>(r,c)*x.at<double>(r,c)+y.at<double>(r,c)*y.at<double>(r,c))'
        return setup+f'next.create(frame.size(),CV_8U);for(int r=0;r<frame.rows;++r)for(int c=0;c<frame.cols;++c)next.at<unsigned char>(r,c)=static_cast<unsigned char>(std::floor(std::min(255.0,({value})*{g})+0.5));'
    mode={'top_hat':'MORPH_TOPHAT','black_hat':'MORPH_BLACKHAT','morph_gradient':'MORPH_GRADIENT'}[kind]
    return f'cv::morphologyEx(frame,next,cv::{mode},cv::getStructuringElement(cv::MORPH_ELLIPSE,cv::Size({params["kernel"]},{params["kernel"]})));'
