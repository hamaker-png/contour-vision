"""Real CPU checks of the bundled object trees, including labeled negatives."""
import base64
import json
from pathlib import Path

import pytest

from backend.engine import decode_image
from backend.models import Measurements, Sample
from backend.optimizer import score
from backend.search_execution import execute
from backend.timeline_exporter import TimelineExportRequest, export_timeline
from backend.timelines import Timeline, execution_plan

ROOT = Path(__file__).resolve().parents[1]


def catalog():
    result = []
    for name in ('photos', 'a', 'b'):
        path = ROOT / f'examples/object-tests-{name}.json'
        if path.exists():
            result.extend(json.loads(path.read_text(encoding='utf-8')))
    return result


def test_twenty_distinct_object_trees_with_three_labeled_training_images():
    examples = catalog()
    assert len(examples) == len({example['id'] for example in examples}) == 20
    assert sum(example['category'] == 'Object tests · photos' for example in examples) == 4
    for example in examples:
        assert len(example['samples']) == len({sample['id'] for sample in example['samples']}) == 3
        assert all(sample['labeled'] and sample['split'] == 'train' for sample in example['samples'])
        assert [bool(sample['boxes']) for sample in example['samples']] == [True, True, False]
        assert example['recommended_timeline_id'] in {pipeline['id'] for pipeline in example['pipelines']}
        assert 2 <= len(example['pipelines']) <= 3
        assert any(pipeline.get('parent_id') for pipeline in example['pipelines'])


@pytest.mark.parametrize('example', catalog(), ids=lambda example:example['id'])
def test_object_tree_recommended_detection_and_export_closure(example):
    graphs = [Timeline.model_validate(value) for value in example['pipelines']]
    measures = Measurements(fields=example['suggested_measurements'])
    selected = example['recommended_timeline_id']
    # Every editable alternative must be type-valid and exportable, including weak baselines.
    for graph in graphs:
        request = TimelineExportRequest(timelines=graphs, selected_timeline_id=graph.id, measurements=measures)
        package = export_timeline(request)
        assert package[:2] == b'PK'
    for definition in example['samples']:
        path = ROOT / 'examples' / definition['filename']
        assert path.resolve().is_relative_to((ROOT / 'examples').resolve())
        data = 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode()
        sample = Sample(id=definition['id'], name=definition['filename'], data=data,
                        boxes=definition['boxes'], labeled=True)
        image = decode_image(data)
        frame, _ = execute(image, graphs, selected, measures)
        result = score(frame, sample)
        assert result['tp'] == len(sample.boxes), (example['id'], sample.name, result)
        assert result['fp'] == result['fn'] == 0, (example['id'], sample.name, result)
        assert frame.details['count'] == definition['expected_count']
        # Alternative outputs are real, valid CPU results; they need not match target labels.
        for graph in graphs:
            if graph.id != selected:
                alternative, _ = execute(image, graphs, graph.id, measures)
                assert alternative.image.size and 'detections' in alternative.details
