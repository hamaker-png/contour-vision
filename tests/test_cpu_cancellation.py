import asyncio
import importlib
import json
import threading
from unittest.mock import AsyncMock, patch

import anyio
import pytest

from backend.cpu_work import WorkCancelled, check_cancelled, run_cpu, run_async
from backend.timelines import TimelineRunRequest, Timeline, Operation, run_timelines
from test_family_workflow import sample


def request():
    return TimelineRunRequest(samples=[sample(),sample('horse.png','second')],timelines=[Timeline(id='main',name='Main',operations=[Operation(id='resize',kind='resize'),Operation(id='gray',kind='grayscale')])])


def test_cancelled_engine_skips_decode_and_stops_before_later_repeats():
    stop=threading.Event();stop.set()
    with patch('backend.graph_execution.decode_image') as decode,pytest.raises(WorkCancelled):
        run_timelines(request(),cancel_event=stop)
    decode.assert_not_called()
    stop.clear()
    from backend.timelines import apply_operation
    calls=[]
    def operation(*args):
        calls.append(args[1].id)
        result=apply_operation(*args)
        if len(calls)==2:stop.set()
        return result
    with patch('backend.graph_execution.apply_operation',operation),pytest.raises(WorkCancelled):
        run_timelines(request(),cancel_event=stop)
    assert calls==['resize','resize']  # warmup, first repeat; no later node/image


class Connection:
    def __init__(self):self.queue=asyncio.Queue();self.watchers=0
    async def receive(self):
        self.watchers+=1
        try:return await self.queue.get()
        finally:self.watchers-=1
    def disconnect(self):self.queue.put_nowait({'type':'http.disconnect'})


def test_cancelled_queue_skips_obsolete_work_and_never_overlaps_workers():
    async def scenario():
        lock=asyncio.Semaphore(1);first,obsolete,latest=Connection(),Connection(),Connection()
        started=threading.Event();calls=[];active=0;maximum=0
        def work(name,cancel_event=None):
            nonlocal active,maximum
            active+=1;maximum=max(maximum,active);calls.append(name)
            try:
                if name=='first':
                    started.set()
                    assert cancel_event.wait(3)
                    check_cancelled(cancel_event)
                return name
            finally:active-=1
        a=asyncio.create_task(run_cpu(first,lock,work,'first'))
        assert await asyncio.to_thread(started.wait,3)
        b=asyncio.create_task(run_cpu(obsolete,lock,work,'obsolete'))
        obsolete.disconnect()
        c=asyncio.create_task(run_cpu(latest,lock,work,'latest'))
        await asyncio.sleep(0)
        first.disconnect()
        results=await asyncio.wait_for(asyncio.gather(a,b,c),4)
        assert [r.status_code for r in results[:2]]==[499,499]
        assert results[2]=='latest' and calls==['first','latest'] and maximum==1
        assert not first.watchers and not obsolete.watchers and not latest.watchers
    asyncio.run(scenario())


def test_actual_body_buffering_middleware_delivers_disconnect_to_worker():
    module=importlib.import_module('backend.app')
    async def scenario():
        body=json.dumps(request().model_dump()).encode();queue=asyncio.Queue();messages=[]
        await queue.put({'type':'http.request','body':body,'more_body':False})
        started=threading.Event();stopped=threading.Event()
        def work(request,cancel_event=None):
            started.set()
            assert cancel_event.wait(3)
            stopped.set();check_cancelled(cancel_event)
        scope={'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'http_version':'1.1','method':'POST','scheme':'http','path':'/api/timelines/run','raw_path':b'/api/timelines/run','query_string':b'','root_path':'','headers':[(b'host',b'testserver'),(b'content-type',b'application/json'),(b'content-length',str(len(body)).encode())],'client':('127.0.0.1',12345),'server':('testserver',80)}
        async def send(message):messages.append(message)
        with patch.object(module,'work_lock',asyncio.Semaphore(1)),patch.object(module,'run_timelines',work):
            task=asyncio.create_task(module.app(scope,queue.get,send))
            assert await asyncio.to_thread(started.wait,3)
            await queue.put({'type':'http.disconnect'})
            await asyncio.wait_for(task,4)
            assert stopped.is_set() and module.work_lock._value==1
    asyncio.run(scenario())


def test_outer_cancellation_stops_thread_before_releasing_lock():
    async def scenario():
        connection=Connection();lock=asyncio.Semaphore(1);started=threading.Event();stopped=threading.Event()
        def work(cancel_event=None):
            started.set()
            assert cancel_event.wait(3)
            stopped.set();check_cancelled(cancel_event)
        async with anyio.create_task_group() as group:
            group.start_soon(run_cpu,connection,lock,work)
            assert await asyncio.to_thread(started.wait,3)
            group.cancel_scope.cancel()
        assert stopped.is_set() and lock._value==1 and not connection.watchers
    asyncio.run(scenario())


def test_raw_asyncio_task_cancel_drains_native_call_before_releasing_lock():
    async def scenario():
        lock=asyncio.Semaphore(1);started=threading.Event();release_native_call=threading.Event();stopped=threading.Event();calls=[]
        def work(name,cancel_event=None):
            calls.append(name)
            if name=='first':
                started.set()
                assert release_native_call.wait(3)
                stopped.set();check_cancelled(cancel_event)
            return name
        first=asyncio.create_task(run_cpu(Connection(),lock,work,'first'))
        assert await asyncio.to_thread(started.wait,3)
        first.cancel()
        latest=asyncio.create_task(run_cpu(Connection(),lock,work,'latest'))
        await asyncio.sleep(.03)
        assert lock.locked() and not stopped.is_set() and calls==['first']
        first.cancel()  # repeated cancellation must not abandon the drain
        release_native_call.set()
        with pytest.raises(asyncio.CancelledError):await first
        assert stopped.is_set() and await latest=='latest' and calls==['first','latest']
    asyncio.run(scenario())


def test_provider_disconnect_cancels_request_and_cleans_up_watcher():
    async def scenario():
        connection=Connection();started=asyncio.Event();stopped=asyncio.Event()
        async def provider():
            started.set()
            try:await asyncio.Event().wait()
            finally:stopped.set()
        task=asyncio.create_task(run_async(connection,provider))
        await asyncio.wait_for(started.wait(),1);connection.disconnect()
        result=await asyncio.wait_for(task,1)
        assert result.status_code==499 and stopped.is_set() and not connection.watchers
        async def succeeds():return {'ok':True}
        assert await run_async(Connection(),succeeds)=={'ok':True}
        async def fails():raise ValueError('Provider unavailable')
        with pytest.raises(ValueError,match='Provider unavailable'):await run_async(Connection(),fails)
    asyncio.run(scenario())


def test_real_suggest_disconnect_after_cpu_evidence_cancels_provider():
    module=importlib.import_module('backend.app')
    async def scenario():
        payload={**request().model_dump(),'description':'Find the objects'}
        body=json.dumps(payload).encode();queue=asyncio.Queue();started=asyncio.Event();stopped=asyncio.Event()
        await queue.put({'type':'http.request','body':body,'more_body':False})
        async def provider(*args):
            started.set()
            try:await asyncio.Event().wait()
            finally:stopped.set()
        scope={'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'http_version':'1.1','method':'POST','scheme':'http','path':'/api/timelines/suggest','raw_path':b'/api/timelines/suggest','query_string':b'','root_path':'','headers':[(b'host',b'testserver'),(b'content-type',b'application/json'),(b'x-openai-key',b'test-key-no-network'),(b'content-length',str(len(body)).encode())],'client':('127.0.0.1',12345),'server':('testserver',80)}
        async def send(message):pass
        with patch.object(module,'work_lock',asyncio.Semaphore(1)),patch.object(module.timeline_ai,'suggest',provider):
            task=asyncio.create_task(module.app(scope,queue.get,send))
            await asyncio.wait_for(started.wait(),2)
            await queue.put({'type':'http.disconnect'})
            await asyncio.wait_for(task,2)
            assert stopped.is_set() and queue.empty() and module.work_lock._value==1
    asyncio.run(scenario())


def _ai_scope(path, body):
    return {'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'http_version':'1.1',
            'method':'POST','scheme':'http','path':path,'raw_path':path.encode(),'query_string':b'',
            'root_path':'','headers':[(b'host',b'testserver'),(b'content-type',b'application/json'),
            (b'x-openai-key',b'test-key-no-network'),(b'content-length',str(len(body)).encode())],
            'client':('127.0.0.1',12345),'server':('testserver',80)}


@pytest.mark.parametrize('path,has_graph', [('/api/analyze',False),('/api/plan',False),
                                         ('/api/timelines/suggest',False),('/api/timelines/suggest',True)])
def test_real_ai_disconnect_during_image_preparation_skips_later_images_and_provider(path,has_graph):
    module=importlib.import_module('backend.app')
    evidence=importlib.import_module('backend.ai_evidence')
    from backend.engine import decode_image
    async def scenario():
        payload={'samples':[sample().model_dump(),sample('horse.png','second').model_dump()],
                 'description':'Find objects'}
        if path.endswith('/suggest'):
            payload['timelines']=[t.model_dump() for t in request().timelines] if has_graph else []
        body=json.dumps(payload).encode();queue=asyncio.Queue();messages=[]
        await queue.put({'type':'http.request','body':body,'more_body':False})
        started=threading.Event();release=threading.Event();calls=[];event_loop_thread=threading.get_ident()
        def held_decode(data):
            calls.append(threading.get_ident())
            started.set()
            assert release.wait(3), 'Image preparation unexpectedly blocked the event loop'
            return decode_image(data)
        provider=AsyncMock(return_value={})
        async def send(message):messages.append(message)
        with patch.object(module,'work_lock',asyncio.Semaphore(1)), \
             patch.object(module.ai,'decode_image',held_decode), \
             patch.object(evidence,'decode_image',held_decode), \
             patch.object(module.ai,'response',provider):
            task=asyncio.create_task(module.app(_ai_scope(path,body),queue.get,send))
            try:
                assert await asyncio.to_thread(started.wait,2)
                await queue.put({'type':'http.disconnect'})
                await asyncio.sleep(.02)
                # A running decoder is drained under the CPU lock before cancellation returns.
                assert module.work_lock.locked() and not task.done()
            finally:
                release.set()
                await asyncio.wait_for(task,4)
            assert calls==[calls[0]] and calls[0]!=event_loop_thread
            assert module.work_lock._value==1 and queue.empty()
            provider.assert_not_awaited()
    asyncio.run(scenario())


@pytest.mark.parametrize('path,has_graph', [('/api/analyze',False),
                                         ('/api/timelines/suggest',False),('/api/timelines/suggest',True)])
def test_real_ai_prepares_each_training_image_once_off_loop_and_reuses_provider_inputs(path,has_graph):
    module=importlib.import_module('backend.app')
    evidence=importlib.import_module('backend.ai_evidence')
    from backend.engine import decode_image
    async def scenario():
        training=[sample(),sample('horse.png','second')]
        payload={'samples':[s.model_dump() for s in training]+[
            {'id':'held','name':'SECRET-VALIDATION','data':'do not decode validation','split':'validation'}],
            'description':'Find objects'}
        if path.endswith('/suggest'):
            payload['timelines']=[t.model_dump() for t in request().timelines] if has_graph else []
        body=json.dumps(payload).encode();queue=asyncio.Queue();messages=[];calls=[]
        await queue.put({'type':'http.request','body':body,'more_body':False})
        event_loop_thread=threading.get_ident()
        def tracked_decode(data):
            calls.append((data,threading.get_ident()))
            return decode_image(data)
        expected=({'observations':'Objects','important_features':[],'questions':[],'limitations':[]}
                  if path.endswith('/analyze') else
                  {'summary':'Check','limitations':[],'timelines':[{'id':'draft','name':'Draft',
                    'parent_id':None,'fork_after':None,'rationale':'Inspect brightness',
                    'operations':[{'id':'draft-gray','kind':'grayscale','params':[]}]}]})
        provider=AsyncMock(return_value=expected)
        async def send(message):messages.append(message)
        with patch.object(module,'work_lock',asyncio.Semaphore(1)), \
             patch.object(module.ai,'decode_image',tracked_decode), \
             patch.object(evidence,'decode_image',tracked_decode), \
             patch.object(module.ai,'response',provider):
            await asyncio.wait_for(module.app(_ai_scope(path,body),queue.get,send),3)
            assert module.work_lock._value==1
        assert next(m['status'] for m in messages if m['type']=='http.response.start')==200
        assert [data for data,_ in calls]==[s.data for s in training]
        assert all(thread!=event_loop_thread for _,thread in calls)
        provider.assert_awaited_once()
        content=provider.call_args.args[2]
        assert 'SECRET-VALIDATION' not in json.dumps(content)
        images=[item['image_url'] for item in content if item['type']=='input_image']
        assert 2<=len(images)<=11
        assert all(max(decode_image(data).shape[:2])<=1280 for data in images)
    asyncio.run(scenario())
