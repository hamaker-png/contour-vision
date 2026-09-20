"""Four offline photo trees using attributed existing photographs and derived tests."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.models import Measurements, Strategy
from backend.timelines import timelines_from_strategies


def build():
    destination = ROOT / 'examples/object-tests'
    destination.mkdir(parents=True, exist_ok=True)
    originals = []
    for filename in ('manifest.json', 'additional-fixtures.json'):
        originals.extend(json.loads((ROOT / 'examples' / filename).read_text(encoding='utf-8')))
    choices = ['red-candies', 'coins', 'red-apple', 'tennis-ball']
    entries = []
    for identifier in choices:
        original = next(item for item in originals if item['id'] == identifier)
        image = cv2.imread(str(ROOT / 'examples' / original['filename']))
        factor = min(1, 960 / max(image.shape[:2]))
        if factor < 1:
            image = cv2.resize(image, (round(image.shape[1] * factor), round(image.shape[0] * factor)), interpolation=cv2.INTER_AREA)
        rotated_boxes = [dict(x=1-b['x']-b['width'], y=1-b['y']-b['height'], width=b['width'], height=b['height']) for b in original['boxes']]
        variants = [('base', image, original['boxes']),
                    ('rotated', cv2.rotate(image, cv2.ROTATE_180), rotated_boxes),
                    ('negative', np.full_like(image, 245), [])]
        samples = []
        for variant, pixels, boxes in variants:
            filename = f'object-tests/photo-{identifier}-{variant}.png'
            assert cv2.imwrite(str(ROOT / 'examples' / filename), pixels)
            samples.append(dict(id=f'{identifier}-{variant}', name=f'{original["title"].split(" · ")[0]} · {variant}',
                                filename=filename, path='/examples/' + filename,
                                split='train', labeled=True, boxes=boxes, expected_count=len(boxes)))
        graphs = timelines_from_strategies([Strategy.model_validate(s) for s in original['strategies']])
        recommended = graphs[2 if identifier == 'coins' else 0].id
        entries.append(dict(
            id=f'object-{identifier}', title=original['title'], filename=samples[0]['filename'],
            path=samples[0]['path'], source=original['source'], credit=original['credit'],
            description=original['description'],
            context=original['context'] + ' Offline teaching set: base photograph, 180-degree derived rotation, and empty background negative. The two positive images are the same capture, not independent validation. All examples are labeled training data; compare the weaker alternative branches too.',
            labeled=True, boxes=original['boxes'], workbench_only=True, collection='object-tests',
            category='Object tests · photos', samples=samples, recommended_timeline_id=recommended,
            suggested_measurements=['length', 'width', 'area', 'color', 'center'],
            pipelines=[graph.model_dump() for graph in graphs],
            expected={'recommended_timeline_id': recommended, 'counts':[sample['expected_count'] for sample in samples]}))
    (ROOT / 'examples/object-tests-photos.json').write_text(json.dumps(entries, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print('Wrote four photo trees with twelve labeled images; original photographs unchanged.')


if __name__ == '__main__':
    build()
