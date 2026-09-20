import asyncio
import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import timeline_ai
from backend.app import app
from backend.engine import data_url
from backend.models import Measurements, Sample, Strategy
from backend.timelines import (Frame, Hardware, Operation, Timeline, TimelineRunRequest, TimelineSuggestRequest,
                               apply_operation, estimate_ms, resolve_paths, run_timelines, timelines_from_strategies)

ROOT = Path(__file__).resolve().parents[1]


def op(kind, id=None, **params):
    return Operation(id=id or kind, kind=kind, params=params)


def sample():
    image = np.full((240,320,3),255,np.uint8)
    cv2.rectangle(image,(70,80),(230,140),(0,0,255),-1)
    return Sample(id="rectangle",name="Rectangle",data=data_url(image)), image


def graph():
    return [Timeline(id="main",name="Color",operations=[op("resize"),op("hsv_mask"),op("contours")]),
            Timeline(id="branch",name="Shape",parent_id="main",fork_after="resize",
                     operations=[op("grayscale"),op("otsu"),op("invert"),op("contours","shape_measure")])]


def test_branch_cache_and_live_prefix():
    timelines = graph()
    request = TimelineRunRequest(samples=[sample()[0]],timelines=timelines)
    result = run_timelines(request)["images"][0]
    assert result["executed_nodes"] == 7  # resize is shared, never timed twice
    assert len(result["stages"]) == 8
    assert result["timelines"][1]["inherited_count"] == 1
    assert result["timelines"][0]["local_ms"] == pytest.approx(sum(result["stages"][o]["local_ms"] for o in ["resize","hsv_mask","contours"]))
    assert result["stages"]["contours"]["details"]["count"] == 1
    # A new parent operation before the stable fork is inherited automatically.
    timelines[0].operations.insert(0,op("median_blur"))
    assert [o.id for o in resolve_paths(timelines)["branch"]][:2] == ["median_blur","resize"]
    # Array order does not change graph semantics.
    backwards = run_timelines(TimelineRunRequest(samples=[sample()[0]],timelines=list(reversed(timelines))))
    assert backwards["images"][0]["stages"]["shape_measure"]["details"]["count"] == 1


def test_reorder_changes_real_pixels_and_invalid_sequence_is_visible():
    s, image=sample()
    image[50:180:2,40:260:2]=0
    frame=Frame(image,"color")
    measure=Measurements()
    gray=apply_operation(frame,op("grayscale"),image,measure)
    threshold=op("threshold",value=127)
    blur=op("gaussian_blur",kernel=9)
    before=apply_operation(apply_operation(gray,blur,image,measure),threshold,image,measure)
    after=apply_operation(apply_operation(gray,threshold,image,measure),blur,image,measure)
    assert not np.array_equal(before.image,after.image)
    assert before.kind=="mask" and after.kind=="gray"
    bad=Timeline(id="bad",name="Wrong order",operations=[op("grayscale"),op("hsv_mask"),op("contours")])
    independent=Timeline(id="ok",name="Still works",operations=[op("hsv_mask","red")])
    result=run_timelines(TimelineRunRequest(samples=[s],timelines=[bad,independent]))["images"][0]
    assert result["stages"]["hsv_mask"]["status"]=="error"
    assert "needs color" in result["stages"]["hsv_mask"]["error"]
    assert result["stages"]["contours"]["status"]=="blocked"
    assert result["stages"]["red"]["status"]=="ok"
    assert result["timelines"][0]["local_ms"] is None


@pytest.mark.parametrize("mutation", [
    lambda t: setattr(t[1],"parent_id","missing"),
    lambda t: setattr(t[1],"fork_after","missing"),
    lambda t: (setattr(t[0],"parent_id","branch"),setattr(t[0],"fork_after","source")),
    lambda t: setattr(t[1].operations[0],"id","resize"),
    lambda t: t[0].operations.pop(0),
])
def test_graph_rejects_dangling_forks_cycles_duplicate_nodes(mutation):
    timelines=graph(); mutation(timelines)
    with pytest.raises(ValueError): resolve_paths(timelines)


@pytest.mark.parametrize("kind,params",[("gaussian_blur",{"kernel":4}),("canny",{"low":200,"high":100}),
                                       ("hsv_mask",{"saturation_low":200,"saturation_high":100}),
                                       ("contours",{"min_area":.5,"max_area":.1}),("threshold",{"invented":1})])
def test_parameters_reject_invalid_configs(kind,params):
    with pytest.raises(ValidationError): Operation(id="step",kind=kind,params=params)


def test_target_estimates_require_evidence_and_scale_in_correct_direction():
    assert estimate_ms(10,Hardware())["ms"]==10
    unknown=estimate_ms(10,Hardware(mode="clock",cpu_name="Many-core processor",architecture="arm64",target_ghz=2))
    assert unknown["ms"] is None
    relative=estimate_ms(10,Hardware(mode="relative",relative_speed=.5))
    assert relative["ms"]==20 and relative["low_ms"]==10 and relative["high_ms"]==40
    clock=estimate_ms(10,Hardware(mode="clock",host_ghz=4,target_ghz=2))
    assert clock["ms"]==20 and clock["high_ms"]==60
    calibrated=estimate_ms(10,Hardware(mode="calibrated",reference_local_ms=4,reference_target_ms=12))
    assert calibrated["ms"]==30 and calibrated["low_ms"]==20


def test_measurement_units_source_color_and_downstream_filtered_mask():
    s,source=sample(); measure=Measurements(fields=["length","width","area","color","center","angle"],pixels_per_unit=2)
    frame=apply_operation(Frame(source,"color"),op("hsv_mask"),source,measure)
    result=apply_operation(frame,op("contours"),source,measure)
    m=result.details["detections"][0]["measurements"]
    assert m=={"length":80,"width":30,"area":2400,"mean_rgb":[255,0,0],"center_px":[150,110],"angle_deg":0}
    assert result.kind=="mask" and result.image.ndim==2 and result.preview.ndim==3
    inverted=apply_operation(result,op("invert"),source,measure)
    assert inverted.image[100,100]==0 and inverted.image[10,10]==255
    smaller=apply_operation(Frame(source,"color"),op("resize",max_side=160),source,measure)
    smaller=apply_operation(smaller,op("hsv_mask"),source,measure)
    measured=apply_operation(smaller,op("contours"),source,measure).details["detections"][0]["measurements"]
    assert measured["length"]==pytest.approx(80,abs=1)


@pytest.mark.parametrize("example_id,winning_index,expected",[("red-candies",0,4),("green-shapes",0,2),("coins",2,24)])
def test_real_internet_photo_and_2d_timeline_presets(example_id,winning_index,expected):
    example=next(e for e in json.loads((ROOT/"examples/manifest.json").read_text()) if e["id"]==example_id)
    s=Sample(id=example_id,name=example["filename"],labeled=True,boxes=example["boxes"],
             data="data:image/png;base64,"+base64.b64encode((ROOT/"examples"/example["filename"]).read_bytes()).decode())
    timelines=timelines_from_strategies([Strategy.model_validate(v) for v in example["strategies"]])
    result=run_timelines(TimelineRunRequest(samples=[s],timelines=timelines))["images"][0]
    assert all(t["errors"]==0 for t in result["timelines"])
    stage=result["stages"][timelines[winning_index].operations[-1].id]
    assert stage["details"]["count"]==expected
    assert stage["details"]["fit"]["f1"]==1
    assert all(v["local_ms"]>0 for k,v in result["stages"].items() if k!="source")


def test_api_serves_explorer_validates_and_runs_graph():
    with TestClient(app) as client:
        assert 'explorer.js' in client.get('/').text
        assert 'detector.js' in client.get('/detector').text
        assert client.get('/static/workflow.mjs').status_code==200
        catalog=client.get('/api/timelines/catalog').json()
        assert len(catalog['operations'])>=17
        body=TimelineRunRequest(samples=[sample()[0]],timelines=graph()).model_dump()
        validated=client.post('/api/timelines/validate',json=body)
        assert validated.status_code==200
        response=client.post('/api/timelines/run',json=body)
        assert response.status_code==200 and response.json()['images'][0]['executed_nodes']==7
        body['samples'][0]['data']='javascript:alert(1)'
        assert client.post('/api/timelines/validate',json=body).status_code==400


def test_ai_suggestion_contains_actual_training_previews_and_validated_graph():
    s,_=sample(); heldout=s.model_copy(update={'id':'private-heldout','name':'Private heldout','split':'validation'})
    request=TimelineSuggestRequest(samples=[s,heldout],description='Find red rectangles',timelines=graph())
    experiment=run_timelines(TimelineRunRequest(samples=[s],timelines=graph()))
    proposal={'summary':'Compare hue against brightness','limitations':['These examples do not prove reliability.'],
              'timelines':[{'id':'draft','name':'Red','parent_id':None,'fork_after':None,'rationale':'Reveal red fill.',
                            'operations':[{'id':'mask','kind':'hsv_mask','params':[{'key':'hue_low','value':170},{'key':'hue_high','value':10}]}]}]}
    mock=AsyncMock(return_value=proposal)
    with patch('backend.timeline_ai.ai.response',mock):
        output=asyncio.run(timeline_ai.suggest(request,'test-key',experiment))
    assert output['timelines'][0]['operations'][0]['params']['hue_low']==170
    content=mock.call_args.args[2]
    assert 'Private heldout' not in json.dumps(content)
    assert sum(c['type']=='input_image' for c in content)>1
    assert 'local_ms' in json.dumps(content)
    assert 'not executable code' in mock.call_args.kwargs['system']
    proposal['timelines'][0]['operations'][0]['kind']='run_python'
    with patch('backend.timeline_ai.ai.response',AsyncMock(return_value=proposal)),pytest.raises(ValueError,match='invalid pipeline'):
        asyncio.run(timeline_ai.suggest(request,'test-key',experiment))


def test_suggestion_endpoint_never_runs_heldout_images():
    s,_=sample(); heldout=s.model_copy(update={'id':'heldout','split':'validation'})
    request=TimelineSuggestRequest(samples=[heldout,s],description='Red object',timelines=graph())
    async def fake(request,key,experiment):
        assert [i['sample_id'] for i in experiment['images']]==['rectangle']
        return {'summary':'Draft only','timelines':[],'limitations':[]}
    with TestClient(app) as client,patch('backend.app.timeline_ai.suggest',fake):
        result=client.post('/api/timelines/suggest',json=request.model_dump(),headers={'X-OpenAI-Key':'test'})
    assert result.status_code==200


@pytest.mark.parametrize('example_id',['red-apple','tennis-ball','horse-silhouette'])
def test_independent_photo_and_silhouette_fixtures(example_id):
    example=next(e for e in json.loads((ROOT/'examples/critic-fixtures.json').read_text()) if e['id']==example_id)
    mime='jpeg' if example['filename'].endswith('.jpg') else 'png'
    sample=Sample(id=example_id,name=example['filename'],labeled=True,boxes=example['boxes'],
                  data=f'data:image/{mime};base64,'+base64.b64encode((ROOT/'examples'/example['filename']).read_bytes()).decode())
    timelines=timelines_from_strategies([Strategy.model_validate(s) for s in example['strategies']])
    image=run_timelines(TimelineRunRequest(samples=[sample],timelines=timelines))['images'][0]
    stage=image['stages'][timelines[0].operations[-1].id]
    assert stage['details']['fit']=={'tp':1,'fp':0,'fn':0,'f1':1}
    assert 5<stage['details']['foreground_pct']<99


def test_a_color_only_detector_exposes_same_color_distractor_failure():
    example=json.loads((ROOT/'examples/manifest.json').read_text())[0]
    image=cv2.imread(str(ROOT/'examples'/example['filename']))
    cv2.circle(image,(115,50),27,(0,0,230),-1)
    sample=Sample(id='confuser',name='Confuser',data=data_url(image),labeled=True,boxes=example['boxes'])
    timelines=timelines_from_strategies([Strategy.model_validate(example['strategies'][0])])
    result=run_timelines(TimelineRunRequest(samples=[sample],timelines=timelines))['images'][0]
    fit=result['stages'][timelines[0].operations[-1].id]['details']['fit']
    assert fit['fp']>=1 and fit['f1']<1
