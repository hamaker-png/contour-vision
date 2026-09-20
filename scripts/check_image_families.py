"""Fixed graphs on six development families. No tuning and no sealed apple holdouts."""
import sys,json,hashlib,datetime
from pathlib import Path
from types import SimpleNamespace
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.models import Strategy,Measurements,Box
from backend.timelines import timelines_from_strategies
from backend.search_execution import execute
from backend.optimizer import score,aggregate
from scripts.critic_benchmark import cases
OUT=ROOT/'artifacts/replay-fixed-family-matrix';OUT.mkdir(parents=True,exist_ok=True)
manifest=json.loads((ROOT/'examples/manifest.json').read_text(encoding='utf-8'))+json.loads((ROOT/'examples/critic-fixtures.json').read_text(encoding='utf-8'))
originals={f['id']:next(cases(f))[2] for f in manifest}
confusers={'red-candies':'red-apple','green-shapes':'tennis-ball','coins':'red-candies','red-apple':'red-candies','tennis-ball':'green-shapes','horse-silhouette':'coins'}
graphs={f['id']:timelines_from_strategies([Strategy.model_validate(s) for s in f['strategies']]) for f in manifest}
frozen={k:[t.model_dump() for t in v] for k,v in graphs.items()}
frozen_sha=hashlib.sha256(json.dumps(frozen,sort_keys=True).encode()).hexdigest()
(OUT/'frozen-graphs.json').write_text(json.dumps(dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sha256=frozen_sha,graphs=frozen,primary_rule='Existing coin preset index2; every other family index0. No selection from this matrix.'),indent=2),encoding='utf-8')

def matrix(f):
    yield from cases(f)
    image=originals[f['id']];h,w=image.shape[:2];boxes=f['boxes'];rng=np.random.default_rng(881)
    yield 'dim_35pct','severe derived stress',np.rint(image*.35).astype(np.uint8),boxes
    shading=np.linspace(.45,1.1,w,dtype=np.float32)[None,:,None]
    yield 'uneven_light','derived robustness',np.clip(image*shading,0,255).astype(np.uint8),boxes
    yield 'noise_sigma25','severe derived stress',np.clip(image.astype(float)+rng.normal(0,25,image.shape),0,255).astype(np.uint8),boxes
    yield 'quarter_resolution','severe derived stress',cv2.resize(image,None,fx=.25,fy=.25,interpolation=cv2.INTER_AREA),boxes
    ok,jpg=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,35]);assert ok
    yield 'jpeg_quality35','derived robustness',cv2.imdecode(jpg,cv2.IMREAD_COLOR),boxes
    rotated=[dict(x=1-b['x']-b['width'],y=1-b['y']-b['height'],width=b['width'],height=b['height']) for b in boxes]
    yield 'rotate_180','derived robustness',cv2.rotate(image,cv2.ROTATE_180),rotated
    yield 'color_removed','declared challenge',cv2.cvtColor(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),cv2.COLOR_GRAY2BGR),boxes
    foreign=confusers[f['id']]
    yield 'foreign_'+foreign,'cross-family real/2D negative',originals[foreign],[]
    if f['id']=='red-candies':
        a=image.copy();cv2.circle(a,(115,50),27,(0,0,230),-1)
        yield 'same_color_disk_distractor','declared challenge',a,boxes
        a=image.copy();cv2.rectangle(a,(250,187),(302,225),(255,255,255),-1)
        yield 'partial_occlusion_full_box','declared challenge',a,boxes

report=dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),frozen_graphs_sha256=frozen_sha,method='Pre-existing fixed per-scene presets. All alternatives scored but never selected using these results. Original scenes are fitted development examples; photometric/geometric changes are dependent stress tests, not independent capture validation. Cross-family images are declared semantic negatives. Occlusion retains the original whole-object box and is explicitly a harder amodal-style challenge.',timing='Single local uncached operation execution; excludes decode, encoding and score. These values are diagnostics, not warmed benchmarks or target hardware estimates.',records=[],families={})
for f in manifest:
    primary=2 if f['id']=='coins' else 0
    for name,group,image,boxes in matrix(f):
        sample=SimpleNamespace(id=f['id']+'-'+name,name=name,boxes=[Box.model_validate(b) for b in boxes])
        for index,t in enumerate(graphs[f['id']]):
            frame,ms=execute(image,graphs[f['id']],t.id,Measurements())
            row=score(frame,sample);row.update(family=f['id'],case=name,group=group,primary=index==primary,candidate=t.name,one_pass_ms=ms,expected=len(boxes),source_width=image.shape[1],source_height=image.shape[0]);report['records'].append(row)
            if index==primary and (row['fp'] or row['fn']):
                preview=(frame.preview if frame.preview is not None else cv2.cvtColor(frame.image,cv2.COLOR_GRAY2BGR)).copy()
                ph,pw=preview.shape[:2]
                for b in boxes:cv2.rectangle(preview,(int(b['x']*pw),int(b['y']*ph)),(int((b['x']+b['width'])*pw),int((b['y']+b['height'])*ph)),(20,20,230),1)
                scale=min(1,720/max(preview.shape[:2]));preview=cv2.resize(preview,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
                cv2.imwrite(str(OUT/(f['id']+'-'+name+'-failure.png')),preview)
    rows=[r for r in report['records'] if r['family']==f['id'] and r['primary']]
    report['families'][f['id']]={g:dict(images=len(rs),**aggregate(rs),failures=[dict(case=r['case'],tp=r['tp'],fp=r['fp'],fn=r['fn']) for r in rs if r['fp'] or r['fn']]) for g in sorted({r['group'] for r in rows}) if (rs:=[r for r in rows if r['group']==g])}
    print(json.dumps({f['id']:report['families'][f['id']]},indent=2),flush=True)
    (OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
report['summary']=dict(families=6,primary_cases=sum(r['primary'] for r in report['records']),all_fixed_graph_executions=len(report['records']),pooled_accuracy='Intentionally not reported: tasks, fitted originals, perturbations and negative/challenge groups differ.')
(OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report['summary'],indent=2),flush=True)
