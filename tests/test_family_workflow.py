import asyncio
import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend import ai, timeline_ai
from backend.app import app
from backend.models import DiscoveryRequest, Sample
from backend.timelines import TimelineSuggestRequest

ROOT=Path(__file__).resolve().parents[1]

def sample(name='smarties.png',id='first',split='train'):
    return Sample(id=id,name=name,split=split,data='data:image/png;base64,'+base64.b64encode((ROOT/'examples'/name).read_bytes()).decode())

def test_family_without_algorithm_can_validate_and_bad_file_is_identified():
    body={'samples':[sample().model_dump()],'timelines':[]}
    with TestClient(app) as client:
        valid=client.post('/api/timelines/validate',json=body)
        assert valid.status_code==200 and valid.json()['timelines']==[]
        body['samples'].append({'id':'broken','name':'broken.png','data':'data:image/png;base64,AAAA'})
        bad=client.post('/api/timelines/validate',json=body)
        assert bad.status_code==400 and 'broken.png' in bad.json()['detail']
        assert client.post('/api/timelines/run',json={'samples':[sample().model_dump()],'timelines':[]}).status_code==422

def test_image_first_discovery_compares_entire_training_family_only():
    request=DiscoveryRequest(samples=[sample(),sample('horse.png','second'),sample('coins.png','held','validation')])
    expected={'observations':'Two different objects','important_features':['shape'],'questions':['Which object matters?'],'limitations':['Different scenes']}
    provider=AsyncMock(return_value=expected)
    with patch('backend.ai.response',provider):
        actual=asyncio.run(ai.discover(request,'test-key'))
    assert actual==expected
    content=provider.call_args.args[2]
    assert sum(x['type']=='input_image' for x in content)==2
    assert 'smarties.png' in json.dumps(content) and 'horse.png' in json.dumps(content)
    assert 'coins.png' not in json.dumps(content)
    assert 'ALL training images as one image family' in provider.call_args.args[3]

def test_discovery_allows_blank_target_but_generation_requires_one():
    result={'observations':'Family','important_features':[],'questions':['What should I find?'],'limitations':[]}
    with TestClient(app) as client,patch('backend.app.ai.discover',AsyncMock(return_value=result)) as discover:
        body={'samples':[sample().model_dump()]}
        assert client.post('/api/analyze',json=body,headers={'X-OpenAI-Key':'test-key'}).status_code==200
        assert discover.call_args.args[0].description==''
        assert client.post('/api/timelines/suggest',json={**body,'description':''}).status_code==422

def test_duplicate_family_ids_rejected_before_ai():
    with TestClient(app) as client,patch('backend.app.ai.discover',AsyncMock()) as discover:
        result=client.post('/api/analyze',json={'samples':[sample().model_dump(),sample().model_dump()]})
        assert result.status_code==422 and not discover.called

def test_ai_draft_rejects_a_color_transform_after_grayscale():
    request=TimelineSuggestRequest(samples=[sample()],description='Find the red candies')
    bad={'summary':'Invalid output','limitations':[],'timelines':[{'id':'a','name':'Bad','parent_id':None,'fork_after':None,'rationale':'Check types','operations':[{'id':'gray','kind':'grayscale','params':[]},{'id':'hsv','kind':'hsv_mask','params':[]}]}]}
    import pytest
    with patch('backend.timeline_ai.ai.response',AsyncMock(return_value=bad)),pytest.raises(ValueError,match='invalid pipeline'):
        asyncio.run(timeline_ai.suggest(request,'test-key'))
