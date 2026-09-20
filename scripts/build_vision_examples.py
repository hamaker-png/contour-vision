"""Reproduce the optional branch-confirmation and synthetic 2D barcode examples."""
import json
import sys
from pathlib import Path
import cv2
import numpy as np
import zxingcpp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.models import Strategy
from backend.timelines import Operation, Timeline, timelines_from_strategies

photo = json.loads((ROOT / 'examples/manifest.json').read_text(encoding='utf-8'))[0]
pipelines = timelines_from_strategies([Strategy.model_validate(s) for s in photo['strategies'][:2]])
pipelines[1].name = 'Dark connected regions'
pipelines[1].operations[-1] = Operation(id='regions', kind='cimg_components', params={'min_pixels':300})
pipelines[1].rationale = 'CImg groups the dark foreground. Inspect missed candy boundaries and merged regions.'
pipelines.append(Timeline(id='confirmed', name='Red + region agreement', parent_id=pipelines[0].id,
    fork_after=pipelines[0].operations[-1].id,
    operations=[Operation(id='agreement', kind='confirm', params={'pipeline_ids':pipelines[1].id})],
    rationale='Overlap confirmation preserves primary measurements. This deliberately imperfect support misses one true red candy: compare the final mask with the primary detector.'))
entries = [{**{k:v for k,v in photo.items() if k!='strategies'},
    'id':'candy-confirmation', 'title':'Branch confirmation · photo', 'workbench_only':True,
    'context':'Compare red contours with independently thresholded CImg regions. The confirmation rejects one true red candy on this photo; agreement can reduce recall. Adjust the support after inspecting its intermediate images. These are editable presets, not AI or proof of reliability.',
    'pipelines':[p.model_dump() for p in pipelines]}]
code = np.asarray(zxingcpp.write_barcode(zxingcpp.BarcodeFormat.QRCode, 'Contour sample 42', width=240, height=240, quiet_zone=12))
cv2.imwrite(str(ROOT / 'examples/qr-code.png'), code)
entries.append({'id':'qr-code', 'title':'Read a QR code · 2D', 'filename':'qr-code.png', 'path':'/examples/qr-code.png',
    'source':'https://github.com/zxing-cpp/zxing-cpp/tree/v2.3.0',
    'credit':'Generated test graphic using ZXing-C++ 2.3.0', 'workbench_only':True,
    'description':'Read the QR code and report its text, format and visible bounds.',
    'context':'Synthetic 2D fixture. Expected text: Contour sample 42. Compare direct color input with grayscale. This is an identity smoke test, not held-out validation.',
    'labeled':False, 'boxes':[], 'pipelines':[
        Timeline(id='direct', name='Direct code reader', operations=[Operation(id='decode', kind='barcode')]).model_dump(),
        Timeline(id='gray', name='Grayscale code reader', operations=[Operation(id='graycode', kind='grayscale'),Operation(id='decodegray', kind='barcode')]).model_dump()]})
path=ROOT/'examples/vision-fixtures.json'
existing=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
ids={e['id'] for e in entries}
path.write_text(json.dumps(entries+[e for e in existing if e['id'] not in ids],indent=2,ensure_ascii=False),encoding='utf-8')
print('Wrote two editable vision examples.')
