"""Evaluate a node DAG once, including confirmation dependencies and truthful costs."""
from collections import Counter
import statistics
import time
import cv2
import numpy as np
from .cpu_work import check_cancelled
from .engine import decode_image,contrast,counts
from .timelines import Frame,resolve_paths,execution_plan,apply_operation,preview_url,estimate_ms,host_info,TIMING_NOTE,ESTIMATE_NOTE
from .vision_params import supporting_ids
from .vision_ops import confirm_frame

def run_graph(request,cancel_event=None):
    check_cancelled(cancel_event)
    paths=resolve_paths(request.timelines);order,previous,dependencies=execution_plan(request.timelines,resolved=paths)
    owners={op.id:t.id for t in request.timelines for op in t.operations}
    closures={t.id:[op.id for op in execution_plan(request.timelines,t.id,paths)[0]] for t in request.timelines}
    image_results=[];pixels=0
    for sample in request.samples:
        check_cancelled(cancel_event);source=decode_image(sample.data);pixels+=source.shape[0]*source.shape[1]
        if pixels>40_000_000:raise ValueError('This batch exceeds 40 megapixels')
        frames={'source':Frame(source,'color')};stages={'source':{'id':'source','status':'ok','kind':'color','image':preview_url(source),'width':source.shape[1],'height':source.shape[0],'local_ms':None,'details':{}}}
        remaining=Counter(node for op in order for node in dependencies[op.id]);executed=0
        for op in order:
            check_cancelled(cancel_event)
            incoming=result=apply=None
            try:
                if any(node not in frames for node in dependencies[op.id]):
                    stages[op.id]={'id':op.id,'status':'blocked','error':'An input or supporting branch failed. Fix that step to continue.','owner_id':owners[op.id]};continue
                incoming=frames[previous[op.id]]
                def apply():
                    if op.kind=='confirm':
                        supports=[(tid,frames[paths[tid][-1].id]) for tid in supporting_ids(op)]
                        return confirm_frame(incoming,supports,op.params,source,request.measurements)
                    return apply_operation(incoming,op,source,request.measurements)
                apply();check_cancelled(cancel_event);durations=[]
                for _ in range(5):
                    check_cancelled(cancel_event);start=time.perf_counter_ns();result=apply();durations.append((time.perf_counter_ns()-start)/1_000_000);check_cancelled(cancel_event)
                ms=statistics.median(durations);details=dict(result.details)
                if result.kind=='mask':details.update({'foreground_pct':round(float(np.mean(result.image>0))*100,2),'separation':contrast(result.image,sample)})
                if 'detections' in details and sample.labeled:
                    tp,fp,fn=counts(details['detections'],sample);details['fit']={'tp':tp,'fp':fp,'fn':fn,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}
                check_cancelled(cancel_event)
                stages[op.id]={'id':op.id,'owner_id':owners[op.id],'status':'ok','kind':result.kind,'width':result.image.shape[1],'height':result.image.shape[0],'image':preview_url(result.preview if result.preview is not None else result.image),'local_ms':ms,'local_range_ms':[min(durations),max(durations)],'target':estimate_ms(ms,request.hardware),'details':details}
                frames[op.id]=result;executed+=1
            except (ValueError,cv2.error) as error:
                message=str(error) if isinstance(error,ValueError) else 'The vision library could not apply this operation. Check its parameters and dimensions.'
                stages[op.id]={'id':op.id,'status':'error','error':message,'owner_id':owners[op.id]}
            finally:
                # Encoded previews and detection records are already in stages.
                # A failed/blocked node also consumes its turn as a DAG reader.
                for node in dependencies[op.id]:
                    remaining[node]-=1
                    if remaining[node]==0:frames.pop(node,None)
                if remaining[op.id]==0:frames.pop(op.id,None)
                # The per-node closure and result must not keep released frames alive.
                incoming=result=apply=None
        summaries=[]
        for pipeline in request.timelines:
            ids=closures[pipeline.id];errors=sum(stages[node]['status']!='ok' for node in ids);elapsed=sum(stages[node].get('local_ms') or 0 for node in ids);target=estimate_ms(elapsed,request.hardware) if not errors else None
            summaries.append({'id':pipeline.id,'path':[op.id for op in paths[pipeline.id]],'dependency_ids':ids,'inherited_count':sum(owners[op.id]!=pipeline.id for op in paths[pipeline.id]),'local_ms':elapsed if not errors else None,'target':target,'errors':errors,'over_budget':bool(target and target['ms'] is not None and target['ms']>request.hardware.budget_ms)})
        image_results.append({'sample_id':sample.id,'stages':stages,'timelines':summaries,'unique_local_ms':sum(s.get('local_ms') or 0 for s in stages.values()),'executed_nodes':executed})
    check_cancelled(cancel_event)
    return {'images':image_results,'hardware':request.hardware.model_dump(),'host':host_info(),'timing_note':TIMING_NOTE,'estimate_note':ESTIMATE_NOTE}
