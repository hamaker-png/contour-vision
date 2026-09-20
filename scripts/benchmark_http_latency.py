"""Measure actual local request/response latency, not only the transform timers."""
import base64
import json
from pathlib import Path
import statistics
import time
import httpx
ROOT=Path(__file__).resolve().parents[1]
records=[]
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=60) as client:
    for example in client.get('/api/examples').json()[:3]:
        timelines=client.get('/api/timelines/presets/'+example['id']).json()['timelines']
        sample={'id':example['id'],'name':example['filename'],'data':'data:image/png;base64,'+base64.b64encode((ROOT/'examples'/example['filename']).read_bytes()).decode()}
        for run in range(5):
            start=time.perf_counter();response=client.post('/api/timelines/run',json={'samples':[sample],'timelines':timelines});response.raise_for_status();response.json()
            records.append({'scene':example['id'],'run':run,'request_response_ms':(time.perf_counter()-start)*1000,'response_bytes':len(response.content)})
values=sorted(r['request_response_ms'] for r in records)
report={'scope':'15 local HTTP round trips, JSON encoding/transfer/decode included; browser paint and the 450ms edit debounce excluded.',
        'median_ms':statistics.median(values),'p95_nearest_rank_ms':values[-1],'records':records}
destination=ROOT/'artifacts/validation/http-latency.json'
destination.parent.mkdir(parents=True,exist_ok=True)
destination.write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='records'},indent=2))
