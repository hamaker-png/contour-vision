"""Six deterministic 2D teaching families; generated development data, not reliability evidence.

Writes only examples/object-tests-b.json and examples/object-tests/b-*.png.
Every recommended path is checked by actual CPU execution against constructed boxes.
"""
import json, math, sys
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.engine import counts,data_url
from backend.models import Measurements,Sample
from backend.search_execution import execute
from backend.timelines import Operation,Timeline,execution_plan

W,H=384,256
DEST=ROOT/'examples/object-tests'
DISCLAIMER='Generated analytic 2D teaching images with constructed labels. All three images are development/training examples; these checks do not establish reliability on camera images, unseen objects or physical measurements.'
def op(id,kind,**params):return Operation(id=id,kind=kind,params=params)
def detect(id,**params):return op(id,'contours',min_area=params.pop('min_area',.001),max_area=params.pop('max_area',.12),**params)
def mask():return np.zeros((H,W),np.uint8)
def box_for(shape):
    x,y,w,h=cv2.boundingRect(shape)
    return dict(x=x/W,y=y/H,width=w/W,height=h/H)
def rectangle(center,size,angle=0):
    shape=mask();cv2.fillConvexPoly(shape,np.rint(cv2.boxPoints((center,size,angle))).astype(np.int32),255)
    return shape
def disk(center,radius):
    shape=mask();cv2.circle(shape,center,radius,255,-1);return shape
def capsule(center,length,width,angle):
    shape=mask();a=math.radians(angle);d=np.array([math.cos(a),math.sin(a)])*(length-width)/2
    p,q=np.rint(np.array(center)-d).astype(int),np.rint(np.array(center)+d).astype(int)
    cv2.line(shape,tuple(p),tuple(q),255,int(width),cv2.LINE_8);return shape
def leaf(center,length,width,angle):
    # Two arcs meet at pointed ends; labels come from this construction, not a detector.
    t=np.linspace(0,1,25);x=(t-.5)*length;y=2*width*t*(1-t)
    points=np.vstack([np.column_stack([x,y]),np.column_stack([x[::-1],-y[::-1]])])
    a=math.radians(angle);rotation=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
    shape=mask();cv2.fillPoly(shape,[np.rint(points@rotation.T+np.array(center)).astype(np.int32)],255);return shape
def paint(image,shape,color,boxes=None):
    image[shape>0]=color
    if boxes is not None:boxes.append(box_for(shape))
def gradient(low,high,vertical=0):
    gray=np.tile(np.linspace(low,high,W),(H,1))+np.linspace(0,vertical,H)[:,None]
    return cv2.cvtColor(np.clip(np.rint(gray),0,255).astype(np.uint8),cv2.COLOR_GRAY2BGR)

def leaves(v):
    image=np.full((H,W,3),(235,242,239),np.uint8);boxes=[]
    layouts=[[(72,66,62,25,-25),(220,79,68,27,30),(156,188,72,29,-10)],
             [(76,184,66,26,25),(221,71,74,30,-40),(284,190,62,25,65)]]
    if v<2:
        for i,(x,y,length,width,angle) in enumerate(layouts[v]):
            paint(image,leaf((x,y),length,width,angle),(45+v*10,135+i*12,48+v*5),boxes)
            a=math.radians(angle);d=np.array([math.cos(a),math.sin(a)])*length*.35
            p,q=np.rint(np.array([x,y])-d).astype(int),np.rint(np.array([x,y])+d).astype(int)
            cv2.line(image,tuple(p),tuple(q),(75,172,80),1)
    paint(image,leaf((305,75),55,23,-20),(40,150,210))
    paint(image,disk((324,180),16),(45,145,50))
    paint(image,leaf((55,205),47,19,12),(55,100,160))
    return image,boxes
def pills(v):
    image=np.full((H,W,3),(68,47,32),np.uint8);boxes=[]
    layouts=[[(70,68,68,22,-20),(202,75,74,23,35),(272,188,68,22,-8)],
             [(76,72,62,21,40),(209,65,69,22,-20),(294,174,72,24,68),(110,190,66,21,5)]]
    if v<2:
        for x,y,length,width,angle in layouts[v]:
            paint(image,capsule((x,y),length,width,angle),(221+v*15,231,241),boxes)
    paint(image,disk((332,60),16),(230,235,240))
    paint(image,rectangle((185,186),(26,26)),(225,231,240))
    if v==2:paint(image,capsule((90,135),76,23,-15),(45,115,170))
    return image,boxes
def pins(v):
    image=gradient(218-v*4,249-v*3,-5);boxes=[]
    layouts=[[(60,67,65,8,-15),(165,77,76,8,20),(284,75,69,8,70),(122,188,82,9,-8)],
             [(55,95,70,8,65),(177,62,74,9,-18),(290,172,80,8,30),(143,184,62,8,0)]]
    if v<2:
        for x,y,length,width,angle in layouts[v]:
            paint(image,rectangle((x,y),(length,width),angle),(30+v*18,)*3,boxes)
    paint(image,disk((318,222),12),(35,)*3)
    paint(image,rectangle((219,192),(25,17),12),(30,)*3)
    if v==2:paint(image,rectangle((120,84),(90,8),20),(160,)*3)
    return image,boxes
def local_marks(v,bright):
    image=gradient(40,155,8) if bright else gradient(106,226,-6)
    if v==1:image=np.flip(image,axis=1).copy()
    boxes=[];layouts=[[(48,66,25,10,0),(136,180,27,11,15),(237,73,26,10,-20),(332,170,25,10,45)],
                     [(55,182,27,10,25),(149,66,24,10,60),(232,173,28,11,-15),(327,75,24,10,0)]]
    if v<2:
        for x,y,length,width,angle in layouts[v]:
            shape=rectangle((x,y),(length,width),angle)
            image[shape>0]=np.clip(image[shape>0].astype(np.int16)+(62 if bright else -62),0,255)
            boxes.append(box_for(shape))
    for center in [(60,122),(194,214),(298,123)]:
        shape=disk(center,5)
        image[shape>0]=np.clip(image[shape>0].astype(np.int16)+(65 if bright else -65),0,255)
    shape=rectangle((190,120),(34,10),-10)
    image[shape>0]=np.clip(image[shape>0].astype(np.int16)+(-30 if bright else 25),0,255)
    return image,boxes
def fiducials(v):
    image=gradient(228-v*4,246-v*4,-4);boxes=[]
    layouts=[[(63,68,37,0),(209,71,39,0),(286,185,41,0)],
             [(75,175,37,-18),(200,72,43,35),(298,181,35,15)]]
    if v<2:
        for x,y,side,angle in layouts[v]:
            paint(image,rectangle((x,y),(side,side),angle),(28+v*10,)*3,boxes)
            paint(image,rectangle((x,y),(side-12,side-12),angle),(239,)*3)
            paint(image,rectangle((x,y),(side/4,side/4),angle),(30,)*3)
    paint(image,rectangle((170,178),(65,11),-10),(35,)*3)
    paint(image,disk((330,48),4),(30,)*3)
    if v==2:
        paint(image,rectangle((82,75),(41,41),18),(150,)*3)
        paint(image,rectangle((278,180),(39,8)),(30,)*3)
        paint(image,rectangle((278,180),(8,39)),(30,)*3)
    return image,boxes

def graphs_for(kind):
    start=op('start','resize',max_side=384);gray=op('gray','grayscale')
    if kind=='leaves':
        return [Timeline(id='main',name='Green hue + elongated shape',rationale='Green hue excludes brown/yellow leaves; elongation excludes the round green token.',operations=[
            start,op('green','hsv_mask',hue_low=35,hue_high=90,saturation_low=65,value_low=45),
            op('clean','morph_open',kernel=3),detect('leaf_objects',min_aspect=1.55,max_aspect=4,min_solidity=.85)]),
            Timeline(id='brightness',name='Brightness-only alternative',parent_id='main',fork_after='start',rationale='Brightness loses the color distinction; compare the brown leaf and green token.',operations=[
                op('brightness_gray','grayscale'),op('brightness_otsu','otsu'),op('brightness_invert','invert'),detect('brightness_objects')]),
            Timeline(id='saturation',name='Saturation + shape alternative',parent_id='main',fork_after='start',rationale='Saturation finds colorful objects but also includes yellow/brown leaves.',operations=[
                op('sat','channel',channel='saturation'),op('sat_threshold','threshold',value=65),detect('sat_objects',min_aspect=1.55,max_aspect=4)])],'main'
    if kind in ('pills','pins','fiducials'):
        params={'pills':dict(min_aspect=1.8,max_aspect=4.5,min_solidity=.9),
                'pins':dict(min_area=.0005,min_aspect=4.5,max_aspect=16,min_solidity=.8),
                'fiducials':dict(min_area=.003,min_aspect=1,max_aspect=1.2,min_solidity=.9)}[kind]
        selection=op('selection','range_mask',low=180 if kind=='pills' else 0,high=255 if kind=='pills' else 90)
        return [Timeline(id='main',name={'pills':'Bright elongated tablets','pins':'Dark elongated pins','fiducials':'Dark square marker outlines'}[kind],
                rationale='Intensity and known shape together reject the constructed distractors. Inspect visible extents before trusting measurements.',
                operations=[start,gray,selection,op('clean','morph_close',kernel=3),detect('objects',**params)]),
            Timeline(id='intensity',name='Intensity without shape filtering',parent_id='main',fork_after='selection',rationale='Keep raw intensity candidates to see why shape constraints matter.',operations=[detect('intensity_objects',min_area=.0003)]),
            Timeline(id='edges',name='Edge contour alternative',parent_id='main',fork_after='gray',rationale='Edges offer a separate outline estimate but may shift thin-object dimensions by a pixel.',operations=[
                op('edges_canny','canny',low=40,high=110),detect('edge_objects',**params)])],'main'
    bright=kind=='solder-pads';filters=dict(min_area=.0005,max_area=.012,min_aspect=1.6,max_aspect=4,min_solidity=.8)
    fixed=[start,gray,op('fixed_threshold','threshold',value=180 if bright else 130)]
    if not bright:fixed.append(op('fixed_invert','invert'))
    fixed.append(detect('fixed_objects',**filters))
    return [Timeline(id='global',name='Global intensity baseline',operations=fixed,rationale='The same global cutoff cannot isolate all marks across this changing background.'),
        Timeline(id='local',name='Top-hat solder-pad detail' if bright else 'Black-hat dark print detail',parent_id='global',fork_after='gray',
            rationale='A kernel wider than each pad removes slow illumination changes; local contrast and elongation retain the intended marks.',
            operations=[op('local_detail','top_hat' if bright else 'black_hat',kernel=31),op('local_mask','range_mask',low=35,high=255),detect('local_objects',**filters)]),
        Timeline(id='edges',name='Direct edge alternative',parent_id='global',fork_after='gray',
            rationale='Compare contour closure and measurements using gradients instead of local background subtraction.',
            operations=[op('edge_detect','canny',low=30,high=85),detect('edge_objects',**filters)])],'local'

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    definitions=[
        ('leaves','Green leaves',leaves,'Find the three green pointed leaves. Ignore the round green token and brown/yellow leaves.',['length','width','color','area']),
        ('pills','Elongated tablets',pills,'Find pale elongated capsule-shaped tablets. Ignore round tablets, pale squares and the orange capsule.',['length','width','angle','color']),
        ('pins','Connector pin lengths',pins,'Find dark long narrow connector pins. Measure visible length; ignore short blocks, round fasteners and pale lines.',['length','width','angle','center']),
        ('solder-pads','Bright solder pads',lambda v:local_marks(v,True),'Find four locally bright elongated solder pads despite changing board brightness. Ignore round spots and dark marks.',['length','width','area','center']),
        ('print-marks','Dark print marks',lambda v:local_marks(v,False),'Find four dark elongated print marks on uneven paper illumination. Ignore round ink spots and bright streaks.',['length','width','angle','center']),
        ('fiducials','Square fiducial outlines',fiducials,'Find three dark separate square marker outlines. Ignore long bars, tiny ink spots, gray squares and plus signs. This detects outlines, not marker identity.',['length','width','center','angle'])]
    entries=[]
    for kind,title,draw,description,fields in definitions:
        graphs,recommended=graphs_for(kind)
        for graph in graphs:execution_plan(graphs,graph.id)
        samples=[];verification=[]
        for variant,label in enumerate(('base','variation','negative')):
            image,boxes=draw(variant);identifier=f'b-{kind}-{label}';filename=f'object-tests/{identifier}.png'
            assert cv2.imwrite(str(ROOT/'examples'/filename),image)
            sample=Sample(id=identifier,name=f'{title} · {label}',data=data_url(image),boxes=boxes,labeled=True,split='train')
            trials=[]
            for graph in graphs:
                result,_=execute(image,graphs,graph.id,Measurements(fields=fields))
                tp,fp,fn=counts(result.details.get('detections',[]),sample)
                trials.append(dict(timeline_id=graph.id,count=result.details.get('count',0),tp=tp,fp=fp,fn=fn))
                if graph.id==recommended:assert (tp,fp,fn)==(len(boxes),0,0),(kind,label,graph.id,tp,fp,fn,result.details)
            samples.append(dict(id=identifier,name=sample.name,filename=filename,path='/examples/'+filename,boxes=boxes,labeled=True,split='train',expected_count=len(boxes),variant=label))
            verification.append(dict(sample_id=identifier,expected_count=len(boxes),pipelines=trials))
        first=samples[0]
        entries.append(dict(id=f'b-{kind}',title=title+' · 2D',category='Object tests · 2D',collection='object-tests',
            filename=first['filename'],path=first['path'],boxes=first['boxes'],labeled=True,source='',
            credit='Generated analytic teaching images · known geometry',description=description,context=DISCLAIMER,workbench_only=True,
            samples=samples,pipelines=[graph.model_dump() for graph in graphs],recommended_timeline_id=recommended,suggested_measurements=fields,
            verification=dict(protocol='Actual CPU execution of all declared pipelines; one-to-one box IoU >= 0.5. Recommended path must have no missed targets or extra detections in each constructed sample.',samples=verification)))
        print(json.dumps(dict(family=kind,samples=len(samples),targets=[s['expected_count'] for s in samples],recommended=recommended,passed=True)),flush=True)
    (ROOT/'examples/object-tests-b.json').write_text(json.dumps(entries,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Wrote six teaching families, 18 images and 18 pipeline definitions; every recommended sample passed.',flush=True)

if __name__=='__main__':main()
