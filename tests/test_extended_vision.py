import cv2
import numpy as np
import pytest
import zxingcpp
from unittest.mock import patch
from pydantic import ValidationError
from backend.engine import data_url
from backend.models import Measurements,Sample
from backend.timelines import Frame,Operation,Timeline,TimelineRunRequest,apply_operation,run_timelines,execution_plan
from backend.vision_ops import confirm_frame,assemble

M=Measurements(fields=['length','width','area','angle','center','color'])
def op(kind,id=None,**params):return Operation(id=id or kind,kind=kind,params=params)
def apply(mask,kind,**params):
    source=np.repeat(mask[:,:,None],3,2) if mask.ndim==2 else mask
    return apply_operation(Frame(mask,'mask' if mask.ndim==2 else 'color'),op(kind,**params),source,M)

def test_cimg_components_holes_connectivity_and_wide_labels():
    a=np.zeros((80,80),np.uint8);a[5:15,5:15]=255;a[8:12,8:12]=0
    f=apply(a,'cimg_components',min_pixels=1)
    assert f.details['count']==1 and f.details['detections'][0]['measurements']['area']==84
    assert np.array_equal(f.image,a)
    a=np.zeros((80,80),np.uint8);a[2:78:3,2:78:3]=255
    assert apply(a,'cimg_components',min_pixels=1).details['count']==676
    a=np.zeros((10,10),np.uint8);a[3,3]=a[4,4]=255
    assert apply(a,'cimg_components',connectivity='4',min_pixels=1).details['count']==2
    assert apply(a,'cimg_components',connectivity='8',min_pixels=1).details['count']==1

def test_cimg_border_and_finite_distance_with_fixed_scale():
    a=np.full((9,9),255,np.uint8)
    assert apply(a,'cimg_components',min_pixels=1).details['count']==0
    assert apply(a,'cimg_components',min_pixels=1,reject_border=False).details['count']==1
    f=apply(a,'cimg_distance',pixels_per_level=.5)
    assert f.image[4,4]==10 and f.image[0,0]==2 and f.kind=='gray'
    assert apply(np.zeros_like(a),'cimg_distance').image.max()==0

def test_circle_and_line_geometry_is_not_recontoured():
    a=np.full((240,320),255,np.uint8);cv2.circle(a,(90,110),35,0,3);cv2.circle(a,(205,110),25,0,3)
    f=apply(a,'hough_circles',min_radius=20,max_radius=40,votes=25,min_distance=60)
    assert f.details['count']==2
    assert all('radius_px' in d['measurements'] for d in f.details['detections'])
    a=np.zeros((100,160),np.uint8);cv2.line(a,(20,45),(130,45),255,1)
    f=apply(a,'hough_lines',votes=20,min_length=70,max_gap=2)
    d=f.details['detections'][0]['measurements']
    assert d['length']>=100 and d['angle_deg']==0 and d['width'] is None and d['area'] is None


def test_circle_search_rejects_expensive_noise_before_native_voting():
    for size,radius,error in [(1024,4,'262,144'),(512,16,'too broad'),(256,64,'too broad')]:
        a=np.random.default_rng(430).integers(0,256,(size,size),dtype=np.uint8)
        with patch('backend.vision_ops.cv2.HoughCircles') as voting,pytest.raises(ValueError,match=error):
            apply(a,'hough_circles',min_radius=1,max_radius=radius,votes=1,min_distance=1)
        voting.assert_not_called()

def test_zxing_decodes_text_without_executing_and_handles_negative():
    text='Contour <tag> & café'
    image=np.asarray(zxingcpp.write_barcode(zxingcpp.BarcodeFormat.QRCode,text,width=180,height=180,quiet_zone=12))
    f=apply(image,'barcode',formats='qr')
    assert f.details['count']==1 and f.details['detections'][0]['measurements']['text']==text
    assert apply(np.full((64,64,3),255,np.uint8),'barcode').details['count']==0

def confirmation_graph():
    # Parent confirms a branch that forks before its confirmation node: valid NODE DAG.
    return [Timeline(id='main',name='Geometry',operations=[op('resize'),op('grayscale'),op('threshold',value=220),op('invert'),op('cimg_components','objects'),op('confirm','agree',pipeline_ids='color')]),
            Timeline(id='color',name='Red',parent_id='main',fork_after='resize',operations=[op('hsv_mask'),op('cimg_components','red')])]

def confirmation_sample():
    source=np.full((160,240,3),255,np.uint8);source[30:80,25:75]=(0,0,200);source[40:100,135:195]=(180,0,0)
    return source,Sample(id='s',name='Two objects',data=data_url(source))

def test_confirmation_evaluates_later_branch_once_and_excludes_rejected_pixels():
    source,s=confirmation_sample();graphs=confirmation_graph();order,previous,deps=execution_plan(graphs)
    assert [o.id for o in order].count('resize')==1
    assert [o.id for o in order].index('red')<[o.id for o in order].index('agree')
    result=run_timelines(TimelineRunRequest(samples=[s],timelines=graphs,measurements=M))['images'][0]
    assert result['stages']['objects']['details']['count']==2 and result['stages']['agree']['details']['count']==1
    assert result['timelines'][0]['local_ms']==pytest.approx(sum(stage.get('local_ms') or 0 for stage in result['stages'].values()))
    frames={'source':Frame(source,'color')}
    for o in order:
        frames[o.id]=confirm_frame(frames[previous[o.id]],[('color',frames['red'])],o.params,source,M) if o.kind=='confirm' else apply_operation(frames[previous[o.id]],o,source,M)
    assert frames['agree'].image[50,50]==255 and frames['agree'].image[60,150]==0
    assert frames['agree'].details['detections'][0]['measurements']['area']==2500

def test_confirmation_cycle_missing_and_empty_support():
    source,s=confirmation_sample();graphs=confirmation_graph()
    graphs[1].operations.append(op('confirm','loop',pipeline_ids='main'))
    with pytest.raises(ValidationError,match='cycle'):TimelineRunRequest(samples=[s],timelines=graphs)
    graphs=confirmation_graph();graphs[0].operations[-1].params['pipeline_ids']='missing'
    with pytest.raises(ValidationError,match='missing'):TimelineRunRequest(samples=[s],timelines=graphs)
    graphs=confirmation_graph();graphs[1].operations[0]=op('hsv_mask',hue_low=45,hue_high=75)
    result=run_timelines(TimelineRunRequest(samples=[s],timelines=graphs))['images'][0]
    assert result['stages']['agree']['status']=='ok' and result['stages']['agree']['details']['count']==0
    graphs[1].operations.insert(0,op('grayscale','bad_gray'))
    result=run_timelines(TimelineRunRequest(samples=[s],timelines=graphs))['images'][0]
    assert result['stages']['agree']['status']=='blocked' and result['timelines'][0]['errors']>0

def test_one_support_blob_cannot_confirm_two_primary_objects():
    shape=(20,30);source=np.zeros((*shape,3),np.uint8)
    def d(box):return {'box':box,'normalized_box':[box[0]/30,box[1]/20,box[2]/30,box[3]/20],'measurements':{}}
    primary=assemble(shape,source,M,[(d([1,2,8,8]),('polygon',np.array([[1,2],[8,2],[8,9],[1,9]]))),(d([10,2,8,8]),('polygon',np.array([[10,2],[17,2],[17,9],[10,9]])))],'Test')
    support=Frame(np.zeros(shape,np.uint8),'mask',details={'detections':[d([1,2,17,8])]})
    result=confirm_frame(primary,[('s',support)],{'min_support':1,'iou':.3,'match_text':False},source,M)
    assert result.details['count']==1 and result.image[4,12]==0


def test_confirmation_comparison_budget_counts_all_supports_before_matching():
    shape=(2,2);source=np.zeros((*shape,3),np.uint8)
    detection={'normalized_box':[0,0,1,1],'measurements':{}}
    primary=Frame(np.zeros(shape,np.uint8),'mask',
                  details={'detections':[detection]*500},regions=[None]*500)
    support=Frame(np.zeros(shape,np.uint8),'mask',details={'detections':[detection]*251})
    # Each support alone is below the cap; together they require 251,000 pairs.
    with patch('backend.vision_ops.overlap') as overlap, pytest.raises(ValueError,match='250,000'):
        confirm_frame(primary,[('a',support),('b',support)],
                      {'min_support':1,'iou':.3,'match_text':False},source,M)
    overlap.assert_not_called()

def test_aliases_cannot_inflate_confirmation_votes():
    source,s=confirmation_sample();graphs=confirmation_graph()
    graphs[0].operations[-1].params.update(pipeline_ids='alias1,alias2',min_support=2)
    graphs.extend([Timeline(id=id,name=id,parent_id='main',fork_after='objects',operations=[]) for id in ('alias1','alias2')])
    with pytest.raises(ValidationError,match='distinct detector results'):TimelineRunRequest(samples=[s],timelines=graphs)

def test_component_color_resizes_the_source_once_per_operation():
    a=np.zeros((40,40),np.uint8);a[3:38:9,3:38:9]=255;source=np.full((80,80,3),120,np.uint8)
    with patch('backend.vision_ops.cv2.resize',wraps=cv2.resize) as resize:
        result=apply_operation(Frame(a,'mask'),op('cimg_components',min_pixels=1),source,M)
    assert result.details['count']==16 and resize.call_count==1
