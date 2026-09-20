"""Reproducible teaching fixtures, explicitly separate from held-out evidence."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.timelines import Operation,Timeline

def op(kind,id=None,**params):return Operation(id=id or kind,kind=kind,params=params)
def entry(id,title,image,boxes,graphs,description,context):
    filename=id+'.png';cv2.imwrite(str(ROOT/'examples'/filename),image)
    return dict(id=id,title=title,filename=filename,path='/examples/'+filename,source='',
        credit='Generated analytic development image · known geometry',description=description,
        context=context,labeled=True,boxes=boxes,workbench_only=True,
        pipelines=[t.model_dump() for t in graphs])

entries=[]
for sign,kind,word in [(1,'top_hat','bright'),(-1,'black_hat','dark')]:
    h,w=160,240;gray=np.tile(np.linspace(40,190,w).astype(np.uint8),(h,1));boxes=[]
    for x in (45,120,195):
        disk=np.zeros((h,w),np.uint8);cv2.circle(disk,(x,80),6,255,-1)
        gray[disk>0]=(gray[disk>0].astype(int)+sign*35).astype(np.uint8)
        boxes.append(dict(x=(x-6)/w,y=74/h,width=13/w,height=13/h))
    base=[op('grayscale','gray'),op('threshold','fixed',value=150)]
    if sign<0:base.append(op('invert'))
    base.append(op('contours','base_detect',min_area=.0003,max_area=.8))
    graphs=[Timeline(id='base',name='Fixed global threshold',operations=base,
        rationale='A fixed global cutoff misses spots on the changing background.'),
        Timeline(id='hat',name='Known-scale local detail',parent_id='base',fork_after='gray',
        rationale='Remove slow background changes, then select the local spot contrast. The kernel must exceed the spot diameter.',
        operations=[op(kind,'hat_step',kernel=31),op('range_mask','select',low=20,high=255),op('contours','hat_detect',min_area=.0003,max_area=.8)])]
    entries.append(entry(word+'-local-detail',word.capitalize()+' spots on a gradient · 2D',gray,boxes,graphs,
        f'Detect the three small {word} round spots across the gradient background.',
        'Constructed 2D teaching example, not held-out reliability evidence. Compare the global cutoff with local morphology. All three radius-6 spots have known locations.'))

image=np.zeros((240,320,3),np.uint8)
cv2.rectangle(image,(58,72),(103,124),(255,255,255),2)
cv2.rectangle(image,(181,150),(218,185),(255,255,255),2)
boxes=[]
for x,y,r in [(220,55,17),(90,185,15)]:
    cv2.circle(image,(x,y),r,(255,255,255),-1)
    boxes.append(dict(x=(x-r)/320,y=(y-r)/240,width=(2*r+1)/320,height=(2*r+1)/240))
graphs=[Timeline(id='main',name='Circle voting',rationale='Circle voting also proposes a circle inside the small rectangle. Inspect the fitted disk.',
    operations=[op('grayscale'),op('hough_circles',min_distance=45,edge_threshold=100,votes=10,min_radius=10,max_radius=28)]),
    Timeline(id='closed_shape',name='Closed circular contour',parent_id='main',fork_after='grayscale',
        rationale='Edges and a circularity filter supply a separate shape check.',
        operations=[op('canny','edge_support',low=50,high=150),op('contours','shape_support',min_area=.001,max_area=.1,min_circularity=.84,max_aspect=1.25)]),
    Timeline(id='confirmed',name='Circles with shape confirmation',parent_id='main',fork_after='hough_circles',
        rationale='Keep fitted circles whose boxes overlap a sufficiently round contour. Primary dimensions are preserved.',
        operations=[op('confirm','agreement',pipeline_ids='closed_shape',iou=.5)])]
entries.append(entry('circle-shape-confirmation','Circles with rectangle confusers · 2D',image,boxes,graphs,
    'Find the two filled circles. Ignore both rectangular outlines. Measure the fitted circle diameter.',
    'Constructed development example based on an observed rectangle false positive. Circle voting returns one extra object; contour confirmation removes it here. Agreement is not a probability of correctness or a promise for new shapes.'))

path=ROOT/'examples/vision-fixtures.json'
existing=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
ids={e['id'] for e in entries}
path.write_text(json.dumps([e for e in existing if e['id'] not in ids]+entries,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('Wrote three analytic teaching examples; preserved other examples.')
