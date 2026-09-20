import cv2
import numpy as np
import pytest
from backend.models import Measurements
from backend.timelines import Frame,Operation,apply_operation,path_kinds
from backend.standard_ops import STANDARD_CATALOG,gamma_table

def apply(image,kind,input_kind='gray',**params):
    source=cv2.cvtColor(image,cv2.COLOR_GRAY2BGR) if image.ndim==2 else image
    return apply_operation(Frame(image,input_kind),Operation(id='op',kind=kind,params=params),source,Measurements())

def test_hole_filling_respects_open_gaps_and_four_connectivity():
    a=np.zeros((15,15),np.uint8);a[2:13,2:13]=255;a[5:10,5:10]=0
    assert apply(a,'fill_holes','mask').image[7,7]==255
    a[0:8,7]=0
    assert apply(a,'fill_holes','mask').image[7,7]==0
    assert np.array_equal(apply(np.full_like(a,255),'fill_holes','mask').image,np.full_like(a,255))
    assert not apply(np.zeros_like(a),'fill_holes','mask').image.any()
    diagonal=np.full((5,5),255,np.uint8);np.fill_diagonal(diagonal,0)
    filled=apply(diagonal,'fill_holes','mask').image
    assert filled[0,0]==0 and filled[2,2]==255 and filled[-1,-1]==0

def test_bright_dark_detail_on_uneven_background():
    image=np.tile(np.linspace(40,160,61).astype(np.uint8),(41,1))
    image[18:23,18:23]=230;image[18:23,38:43]=10
    top=apply(image,'top_hat',kernel=15).image;black=apply(image,'black_hat',kernel=15).image
    assert top[20,20]>100 and top[20,40]==0
    assert black[20,40]>90 and black[20,20]==0

def test_sobel_retains_both_polarities_with_fixed_gain():
    image=np.zeros((21,31),np.uint8);image[:,10:21]=100
    gradient=apply(image,'sobel',direction='x',gain=.25).image
    assert gradient[10,9]==gradient[10,21]==100
    assert not apply(image,'sobel',direction='y').image.any()
    assert apply(image,'sobel',gain=.5).image[10,9]==200
    assert apply(image,'sobel',gain=4).image[10,9]==255

def test_inclusive_range_gamma_and_binary_gradient():
    ramp=np.arange(256,dtype=np.uint8).reshape(16,16)
    assert np.count_nonzero(apply(ramp,'range_mask',low=64,high=127).image)==64
    assert np.array_equal(apply(ramp,'gamma').image,ramp)
    assert gamma_table(.5)[64]>64 and gamma_table(2)[64]<64
    mask=np.zeros((15,15),np.uint8);mask[5:10,5:10]=255
    result=apply(mask,'morph_gradient','mask',kernel=3)
    assert result.kind=='mask' and set(np.unique(result.image))=={0,255}
    assert result.image[7,7]==0 and result.image[5,7]==255

def test_standard_parameter_and_type_guards():
    with pytest.raises(ValueError):Operation(id='x',kind='range_mask',params={'low':200,'high':20})
    with pytest.raises(ValueError):Operation(id='x',kind='top_hat',params={'kernel':16})
    with pytest.raises(ValueError):Operation(id='x',kind='sobel',params={'kernel':9})
    with pytest.raises(ValueError):path_kinds([Operation(id='x',kind='fill_holes')])
    assert len(STANDARD_CATALOG)==7


def test_sobel_uses_stable_half_up_rounding_on_integer_border_gradients():
    # A half intensity must not change with OpenCV's approximate float magnitude.
    rng=np.random.default_rng(118)
    image=rng.integers(0,256,(19,23),dtype=np.uint8)
    for kernel in (3,5,7):
        for gain in (.001,.25,1.125):
            x=cv2.Sobel(image,cv2.CV_64F,1,0,ksize=kernel)
            y=cv2.Sobel(image,cv2.CV_64F,0,1,ksize=kernel)
            expected=np.array([[min(255,int((float(a*a+b*b)**.5)*gain+.5)) for a,b in zip(xs,ys)] for xs,ys in zip(x,y)],dtype=np.uint8)
            assert np.array_equal(apply(image,'sobel',kernel=kernel,gain=gain).image,expected)


def test_contour_color_roi_and_bounded_object_count():
    from backend.timelines import contour_frame
    source=np.zeros((80,100,3),np.uint8);source[:]=(100,30,10)
    source[20:40,30:60]=(17,83,219)
    mask=np.zeros(source.shape[:2],np.uint8);mask[20:40,30:60]=255
    params=Operation(id='c',kind='contours').params
    frame=contour_frame(mask,source,params,Measurements(fields=['color']))
    assert frame.details['detections'][0]['measurements']['mean_rgb']==[219,83,17]
    crowded=np.zeros((175,175),np.uint8)
    for y in range(0,175,5):
        for x in range(0,175,5):crowded[y:y+3,x:x+3]=255
    params=Operation(id='c',kind='contours',params={'min_area':.00001}).params
    with pytest.raises(ValueError,match='1,000|1000'):
        contour_frame(crowded,cv2.cvtColor(crowded,cv2.COLOR_GRAY2BGR),params,Measurements())
