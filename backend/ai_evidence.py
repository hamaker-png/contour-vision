"""Compact real training evidence: one pass, shared work, at most nine previews."""
import cv2
from .cpu_work import check_cancelled
from .engine import decode_image,counts,working_image,data_url
from .timelines import resolve_paths,preview_url
from .search_execution import execute,FrameCache

def prepare_evidence(request,cancel_event=None):
    graph=resolve_paths(request.timelines)
    ids=list(graph)
    if request.focus_timeline_id:
        if request.focus_timeline_id not in graph:raise ValueError('Select an existing pipeline for AI review.')
        ids.remove(request.focus_timeline_id);ids.insert(0,request.focus_timeline_id)
    ids=[id for id in ids if graph[id]][:3]
    training=[s for s in request.samples if s.split=='train'];family=[];stages={};paths=[];total_pixels=0;image_inputs={}
    if not training:raise ValueError('Add training images before asking the AI')
    for index,sample in enumerate(training):
        check_cancelled(cancel_event);source=decode_image(sample.data);total_pixels+=source.shape[0]*source.shape[1]
        if total_pixels>40_000_000:raise ValueError('The training family exceeds 40 megapixels.')
        image_inputs[sample.id]=data_url(working_image(source)[0])
        cache=FrameCache();record={'sample_id':sample.id,'name':sample.name,'labeled':sample.labeled,'pipelines':[]}
        for id in ids:
            trace={};preview_ids={op.id for op in graph[id][-3:]} if index==0 else set()
            elapsed=None
            try:
                final,elapsed=execute(source,request.timelines,id,request.measurements,cache,cancel_event,trace=trace,trace_ids=preview_ids)
                details={'id':id,'status':'ok','count':final.details.get('count'),'screen_ms':elapsed}
                if sample.labeled and 'detections' in final.details:
                    tp,fp,fn=counts(final.details['detections'],sample);details['fit']={'tp':tp,'fp':fp,'fn':fn,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}
            except (ValueError,cv2.error) as error:
                # An experimental path can fail while another is useful. Preserve
                # that evidence so the model can explain or repair the bad path.
                details={'id':id,'status':'error','error':str(error)[:300],'screen_ms':None}
            record['pipelines'].append(details)
            if index==0:
                paths.append({'id':id,'path':[op.id for op in graph[id]],'screen_ms':elapsed})
                for oid,(frame,duration) in trace.items():
                    if oid in stages:continue
                    info=dict(frame.details)
                    if 'detections' in info:info['detections']=info['detections'][:15]
                    stages[oid]={'id':oid,'kind':frame.kind,'width':frame.image.shape[1],'height':frame.image.shape[0],'screen_ms':duration,'details':info,'image':preview_url(frame.preview if frame.preview is not None else frame.image)}
        family.append(record)
    return {'images':[{'sample_id':training[0].id,'timelines':paths,'stages':stages}],'family_summary':family,'image_inputs':image_inputs,
        'timing_note':'Single-pass screening times, not five-run medians or deployment benchmarks. Shared operation cost is included in every relevant path.',
        'estimate_note':'No target-hardware guarantee follows from screening timings.'}
