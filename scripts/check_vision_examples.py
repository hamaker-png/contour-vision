"""Exercise the served example graphs and preserve every intermediate preview."""
import base64
import json
import math
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
destination = ROOT / 'artifacts/vision-examples'
destination.mkdir(parents=True, exist_ok=True)
records = []
with httpx.Client(base_url='http://127.0.0.1:8000', timeout=60) as client:
    assert client.get('/api/health').json()['cpu_only'] is True
    assert len(client.get('/api/timelines/catalog').json()['operations']) == 30
    assert client.get('/static/favicon.svg').status_code == 200
    examples = [example for example in client.get('/api/examples').json() if example.get('collection') != 'object-tests']
    assert len(examples) == 11
    for example in examples:
        preset = client.get('/api/timelines/presets/' + example['id'])
        preset.raise_for_status()
        response = client.post('/api/timelines/run', json={
            **preset.json(), 'samples':[{'id':example['id'], 'name':example['filename'],
                'data':'data:image/png;base64,' + base64.b64encode((ROOT/'examples'/example['filename']).read_bytes()).decode(),
                'labeled':example['labeled'], 'boxes':example['boxes']}],
            'hardware':{'mode':'relative','relative_speed':.5,'cpu_name':'Example half-speed CPU'},
            'measurements':{'fields':['length','width','area','angle','color','center']}})
        response.raise_for_status()
        result = response.json()['images'][0]
        directory = destination / example['id']
        directory.mkdir(exist_ok=True)
        for stage in result['stages'].values():
            assert stage['status']=='ok', stage
            if stage['id'] != 'source':
                assert stage['target']['estimated'] is True
                assert math.isclose(stage['target']['ms'], 2 * stage['local_ms'])
            preview = stage.pop('image', None)
            if preview:
                (directory / (stage['id'] + '.png')).write_bytes(base64.b64decode(preview.split(',',1)[1]))
        for pipeline in result['timelines']:
            assert not pipeline['errors']
            assert math.isclose(pipeline['local_ms'], sum(result['stages'][node]['local_ms']
                                                         for node in pipeline['dependency_ids']))
            assert math.isclose(pipeline['target']['ms'], 2 * pipeline['local_ms'])
            final = result['stages'][pipeline['path'][-1]]
            records.append({'example':example['id'], 'pipeline':pipeline['id'], 'count':final['details']['count'],
                'fit':final['details'].get('fit'), 'local_ms':pipeline['local_ms'],
                'target_estimate':pipeline['target'], 'dependencies':pipeline['dependency_ids']})
            if example['id']=='qr-code':
                assert final['details']['count']==1
                assert final['details']['detections'][0]['measurements']['text']=='Contour sample 42'
        if example['id']=='candy-confirmation':
            assert result['stages']['agreement']['details']['fit']=={'tp':3,'fp':0,'fn':1,'f1':6/7}
        if example['id'] in ('bright-local-detail','dark-local-detail'):
            assert result['stages']['hat_detect']['details']['fit']=={'tp':3,'fp':0,'fn':0,'f1':1}
            assert result['stages']['base_detect']['details']['fit']['fn']>0
        if example['id']=='circle-shape-confirmation':
            assert result['stages']['hough_circles']['details']['fit']=={'tp':2,'fp':1,'fn':0,'f1':.8}
            assert result['stages']['agreement']['details']['fit']=={'tp':2,'fp':0,'fn':0,'f1':1}
        (directory / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
(destination / 'summary.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
print(json.dumps(records, indent=2))
