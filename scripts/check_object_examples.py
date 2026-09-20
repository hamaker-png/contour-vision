"""Run the 20 object trees through the live local API and retain previews/projects."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'artifacts/object-examples'
DEST.mkdir(parents=True, exist_ok=True)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def main():
    records = []
    workspace_files = []
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=90) as client:
        catalog = client.get('/api/examples')
        catalog.raise_for_status()
        examples = [example for example in catalog.json() if example.get('collection') == 'object-tests']
        assert len(examples) == 20
        for example in examples:
            preset = client.get('/api/timelines/presets/' + example['id'])
            preset.raise_for_status()
            samples = []
            for definition in example['samples']:
                image = client.get(definition['path'])
                image.raise_for_status()
                samples.append(dict(id=definition['id'], name=definition.get('name', definition['filename']),
                                    data='data:image/png;base64,'+base64.b64encode(image.content).decode(),
                                    split='train', labeled=True, boxes=definition['boxes']))
            body = dict(samples=samples, timelines=preset.json()['timelines'],
                        measurements={'fields': example['suggested_measurements'], 'pixels_per_unit':0, 'unit':'mm'})
            response = client.post('/api/timelines/run', json=body)
            response.raise_for_status()
            result = response.json()
            directory = DEST / example['id']
            directory.mkdir(exist_ok=True)
            selected = example['recommended_timeline_id']
            selected_name = next(pipeline['name'] for pipeline in body['timelines'] if pipeline['id'] == selected)
            rows = []
            for definition, image in zip(example['samples'], result['images'], strict=True):
                assert definition['id'] == image['sample_id']
                preview_directory = directory / definition['id']
                preview_directory.mkdir(exist_ok=True)
                for stage in image['stages'].values():
                    assert stage['status'] == 'ok', (example['id'], definition['id'], stage)
                    preview = stage.pop('image', None)
                    if preview:
                        (preview_directory / (stage['id']+'.png')).write_bytes(base64.b64decode(preview.split(',',1)[1]))
                outcomes = []
                for pipeline in image['timelines']:
                    assert pipeline['errors'] == 0
                    final = image['stages'][pipeline['path'][-1]]['details']
                    outcomes.append({'pipeline':pipeline['id'], 'count':final['count'], 'fit':final['fit']})
                    if pipeline['id'] == selected:
                        assert final['count'] == definition['expected_count']
                        assert final['fit']['tp'] == len(definition['boxes'])
                        assert final['fit']['fp'] == final['fit']['fn'] == 0, (example['id'], definition['id'], final['fit'])
                rows.append({'sample':definition['id'], 'expected_count':definition['expected_count'], 'outcomes':outcomes})
            project = dict(version=1, **body, description=example['description'], context=example['context']+' Suggested starting pipeline: '+selected_name+'.',
                           recommended_timeline_id=selected, answers='', guidance={'answers':[], 'discovery':None})
            # All images are training fixtures. Omitted provenance remains conservative on import.
            project_path = directory / (example['id']+'.json')
            write_json(project_path, project)
            workspace_files.append(project_path)
            export_response = client.post('/api/timelines/export', json={
                'timelines':body['timelines'], 'selected_timeline_id':selected, 'measurements':body['measurements']})
            export_response.raise_for_status()
            (directory / 'selected-cpp.zip').write_bytes(export_response.content)
            write_json(directory / 'results.json', result)
            row = {'id':example['id'], 'title':example['title'], 'category':example['category'],
                   'selected_pipeline':selected, 'selected_pipeline_name':selected_name, 'pipelines':len(body['timelines']),
                   'measurements':example['suggested_measurements'], 'samples':rows,
                   'source':example['source'], 'credit':example['credit']}
            records.append(row)
            print(f'{example["title"]}: 3 images passed; {len(body["timelines"])} editable paths', flush=True)
    summary = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), object_trees=len(records),
                   image_cases=sum(len(row['samples']) for row in records),
                   pipeline_executions=sum(len(sample['outcomes']) for row in records for sample in row['samples']),
                   local_api_only=True, limitations='Constructed 2D teaching sets and dependent photo variations, not deployment reliability evidence.',
                   examples=records)
    write_json(DEST / 'report.json', summary)
    lines = ['# 20 offline object trees', '',
             'Choose a tree under **Images → Example trees · no API key** in the app. Each has two positive practice images, one labeled negative, and editable alternatives. All three images run automatically.', '',
             'These are known teaching examples. Photo variants reuse the same capture; generated 2D objects do not establish performance on real-world photographs. Alternative paths may intentionally detect extra objects or use different measurement definitions.', '',
             '| Object | Starting pipeline | Measurements |', '|---|---|---|']
    lines.extend(f'| {row["title"]} | {row["selected_pipeline_name"]} | {", ".join(row["measurements"])} |' for row in records)
    lines.extend(['', 'The companion ZIP contains 20 saved projects with embedded images. Extract it and use **Open project**. No API key is included or required. The intended starting pipeline is selected on import; use **Run all images**.', '',
                  'Sources and licenses: see examples/SOURCES.md in the repository. Photo credits:'])
    lines.extend(f'- [{row["title"]}]({row["source"]}): {row["credit"]}' for row in records if row['source'])
    readme = DEST / 'README.md'
    readme.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    with zipfile.ZipFile(DEST / '20-object-trees.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(readme, 'README.md')
        for path in workspace_files:
            archive.write(path, path.name)
    print(json.dumps({key:summary[key] for key in ('object_trees','image_cases','pipeline_executions','local_api_only')}, indent=2))


if __name__ == '__main__':
    main()
