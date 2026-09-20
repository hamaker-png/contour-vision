"""Run existing compiled exports on fresh small inputs; run the compiled export matrix without tuning."""
import sys,json,hashlib,subprocess,datetime
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.models import Measurements
from backend.timelines import Frame,Operation,apply_operation
from scripts.benchmark_examples import cases
OUT=ROOT/'artifacts/replay-native-variability';OUT.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(29191)
for h,w in [(1,1),(1,9),(9,1),(3,3),(8,13)]:
    for _ in range(8):rng.random((h,w))
images=[('rounding_border',rng.integers(0,256,(17,21),dtype=np.uint8))]
for h,w in [(1,1),(1,9),(9,1),(13,16),(19,35),(64,65)]:images.append((f'random_{h}_{w}',rng.integers(0,256,(h,w),dtype=np.uint8)))
images += [('ramp_256',np.tile(np.arange(256,dtype=np.uint8),(17,1))),('zero',np.zeros((19,25),np.uint8)),('white',np.full((19,25),255,np.uint8))]
ring=np.zeros((35,41),np.uint8);ring[1:-1,1:-1]=255;ring[5:-5,5:-5]=0;ring[0,0]=255;images.append(('ring_holes',ring))
manifest=json.loads((ROOT/'examples/manifest.json').read_text(encoding='utf-8'))+json.loads((ROOT/'examples/additional-fixtures.json').read_text(encoding='utf-8'))
for f in manifest:
    _,_,a,_=next(cases(f));scale=min(1,512/max(a.shape[:2]));a=cv2.resize(a,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    images.append((f['id'],a))
images=[(name,cv2.cvtColor(a,cv2.COLOR_GRAY2BGR) if a.ndim==2 else a) for name,a in images]
for name,a in images:cv2.imwrite(str(OUT/(name+'.png')),a)
report=dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),python_opencv=cv2.__version__,scope='Existing seven compiled export configurations, varied independent arrays and downscaled existing development examples. No recompile, tuning, or sealed apple holdouts.',records=[])
for kind in ['top_hat','black_hat','sobel','range_mask','morph_gradient','gamma','fill_holes']:
    directory=ROOT/'artifacts/expanded-native'/kind;binary=directory/'build/detector.exe';binaryhash=hashlib.sha256(binary.read_bytes()).hexdigest();config=json.loads((directory/'config.json').read_text(encoding='utf-8'));ops=[Operation.model_validate(x) for x in config['operations']];measure=Measurements.model_validate(config['measurements'])
    for name,source in images:
        target=OUT/(kind+'-'+name+'.png');actual=json.loads(subprocess.check_output([str(binary),'--output',str(target),str(OUT/(name+'.png'))],text=True))
        frame=Frame(source,'color')
        for op in ops:frame=apply_operation(frame,op,source,measure)
        native=cv2.imread(str(target),cv2.IMREAD_UNCHANGED);delta=abs(native.astype(np.int16)-frame.image.astype(np.int16));indices=np.argwhere(delta)
        record=dict(operation=kind,image=name,width=source.shape[1],height=source.shape[0],binary_sha256=binaryhash,pixel_differences=len(indices),max_abs_difference=int(delta.max()),native_ms=actual['latency_ms'],examples=[dict(y=int(q[0]),x=int(q[1]),python=int(frame.image[tuple(q)]),native=int(native[tuple(q)])) for q in indices[:8]])
        report['records'].append(record)
        if len(indices):print(json.dumps(record),flush=True)
    print(kind,'done',flush=True)
report['summary']={kind:dict(cases=sum(r['operation']==kind for r in report['records']),mismatched_cases=sum(r['operation']==kind and r['pixel_differences']>0 for r in report['records']),pixel_differences=sum(r['pixel_differences'] for r in report['records'] if r['operation']==kind),max_abs_difference=max(r['max_abs_difference'] for r in report['records'] if r['operation']==kind)) for kind in ['top_hat','black_hat','sobel','range_mask','morph_gradient','gamma','fill_holes']}
(OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report['summary'],indent=2),flush=True)
