"""Separate mask fidelity and measurement errors from bounding-box detection scores."""
import json
import sys
from pathlib import Path
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.models import Measurements,Strategy
from backend.timelines import Frame,Operation,apply_operation,resolve_paths,timelines_from_strategies

fields=Measurements(fields=['length','width','area','angle','color','center'])
horse=cv2.imread(str(ROOT/'examples/horse.png'));truth=cv2.cvtColor(horse,cv2.COLOR_BGR2GRAY)<127
fixture=next(e for e in json.loads((ROOT/'examples/critic-fixtures.json').read_text()) if e['id']=='horse-silhouette')
timelines=timelines_from_strategies([Strategy.model_validate(s) for s in fixture['strategies']]);paths=resolve_paths(timelines)
masks=[]
for t in timelines:
    frame=Frame(horse,'color')
    for op in paths[t.id]:frame=apply_operation(frame,op,horse,fields)
    predicted=frame.image>0
    masks.append({'timeline':t.name,'mask_iou':float(np.logical_and(predicted,truth).sum()/np.logical_or(predicted,truth).sum()),
                  'missed_foreground_pixels':int((truth&~predicted).sum()),'extra_foreground_pixels':int((predicted&~truth).sum())})
records=[]
for scale in [.5,1,2]:
    for angle in [0,17,53]:
        source=np.full((round(300*scale),round(400*scale),3),255,np.uint8)
        rectangle=((200*scale,150*scale),(160*scale,60*scale),angle)
        points=np.round(cv2.boxPoints(rectangle)).astype(np.int32);cv2.fillConvexPoly(source,points,(0,0,255))
        for side in [128,1280]:
            frame=Frame(source,'color')
            for i,(kind,params) in enumerate([('resize',{'max_side':side}),('hsv_mask',{}),('contours',{})]):
                frame=apply_operation(frame,Operation(id=f's{i}',kind=kind,params=params),source,fields)
            m=frame.details['detections'][0]['measurements'];difference=abs(m['angle_deg']-angle)
            records.append({'scale':scale,'angle':angle,'max_side':side,'expected_length_px':160*scale,'expected_width_px':60*scale,
                            'measured':m,'length_error_pct':abs(m['length']-160*scale)/(160*scale)*100,
                            'width_error_pct':abs(m['width']-60*scale)/(60*scale)*100,'angle_error_deg':min(difference,180-difference),
                            'max_rgb_channel_error':max(abs(a-b) for a,b in zip(m['mean_rgb'],[255,0,0]))})
report={'scope':'Analytic raster rectangles, not calibrated real-camera measurement certification. Low resolution intentionally tests the speed/precision tradeoff.',
        'horse_mask_fidelity':masks,'rectangles':records}
destination=ROOT/'artifacts/critic/measurement-evidence.json';destination.write_text(json.dumps(report,indent=2))
print(json.dumps({'horse_masks':masks,'errors_by_max_side':{side:{key:max(r[key] for r in records if r['max_side']==side) for key in ['length_error_pct','width_error_pct','angle_error_deg','max_rgb_channel_error']} for side in [128,1280]}},indent=2))
