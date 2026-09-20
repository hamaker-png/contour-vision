import io
import json
import zipfile
import pytest
from pydantic import ValidationError
from backend.timeline_exporter import TimelineExportRequest,export_timeline
from backend.timelines import Timeline,Operation

def test_exact_shared_prefix_is_exported_without_secret_or_unused_branch():
    timelines=[Timeline(id='a',name='Unicode 🍏',operations=[Operation(id='resize',kind='resize'),Operation(id='mask',kind='hsv_mask')]),
               Timeline(id='b',name='Edited child',parent_id='a',fork_after='resize',operations=[Operation(id='gray',kind='grayscale'),Operation(id='threshold',kind='otsu')])]
    request=TimelineExportRequest(timelines=timelines,selected_timeline_id='b')
    with zipfile.ZipFile(io.BytesIO(export_timeline(request))) as archive:
        config=json.loads(archive.read('config.json'));source=archive.read('detector.cpp').decode()
        assert [o['id'] for o in config['operations']]==['resize','gray','threshold']
        assert 'cv::inRange' not in source and 'cv::cvtColor(frame,next,cv::COLOR_BGR2GRAY)' in source
        assert source.index('cv::resize(frame,next')<source.index('cv::cvtColor(frame,next')<source.index('cv::threshold(frame,next')
        assert 'OPENAI_API_KEY' not in source
        assert set(archive.namelist())=={'detector.cpp','CMakeLists.txt','README.md','config.json'}

def test_export_rejects_invalid_input_order_and_unknown_selection():
    t=Timeline(id='a',name='Invalid',operations=[Operation(id='gray',kind='grayscale'),Operation(id='mask',kind='hsv_mask')])
    with pytest.raises(ValidationError,match='Cannot export'):TimelineExportRequest(timelines=[t],selected_timeline_id='a')
    with pytest.raises(ValidationError,match='existing pipeline'):TimelineExportRequest(timelines=[t],selected_timeline_id='missing')
