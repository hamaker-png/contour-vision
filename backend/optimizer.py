"""Bounded search with an immutable baseline and explicit training-only evidence."""
import copy,hashlib,json,statistics,time
from types import SimpleNamespace
import cv2
from pydantic import Field,model_validator
from .models import StrictModel
from .timelines import Timeline,TimelineRunRequest,resolve_paths,execution_plan,preview_url,estimate_ms
from .graph_exporter import validate_export_graph
from .vision_params import DETECTORS,supporting_ids
from .engine import decode_image,iou
from .cpu_work import check_cancelled
from .search_execution import FrameCache,execute,SearchDeadline

class Seed(StrictModel):
    name:str=Field(default='Proposed alternative',max_length=100)
    timelines:list[Timeline]=Field(min_length=1,max_length=8)
    selected_timeline_id:str

class OptimizeRequest(TimelineRunRequest):
    selected_timeline_id:str
    seeds:list[Seed]=Field(default_factory=list,max_length=3)
    max_trials:int=Field(default=32,ge=4,le=96)
    budget_seconds:float=Field(default=20,ge=2,le=60)
    @model_validator(mode='after')
    def eligible(self):
        training=[s for s in self.samples if s.split=='train']
        if not training or any(not s.labeled for s in training):raise ValueError('Label every target in each training image and confirm labels before optimization. Validation images are not used.')
        if not any(s.boxes for s in training):raise ValueError('Include at least one labeled positive training image; negatives alone cannot establish target detection.')
        for candidate in [self,*self.seeds]:
            resolved,*_=validate_export_graph(candidate)
            if not resolved[candidate.selected_timeline_id] or resolved[candidate.selected_timeline_id][-1].kind not in DETECTORS:raise ValueError('Optimization needs a pipeline ending in an object detector.')
        return self

def compact_graph(graphs,selected):
    order,_,_=execution_plan(graphs,selected);ids={op.id for op in order}
    needed={selected};by_id={t.id:t for t in graphs}
    needed.update(t.id for t in graphs if any(op.id in ids for op in t.operations))
    needed.update(reference for op in order for reference in supporting_ids(op))
    for tid in list(needed):
        parent=by_id[tid].parent_id
        while parent:needed.add(parent);parent=by_id[parent].parent_id
    result=[]
    for t in graphs:
        if t.id in needed:
            clone=t.model_copy(deep=True);clone.operations=[op for op in clone.operations if op.id in ids];result.append(clone)
    return result

def signature(graphs,selected):
    # Stable across operation and pipeline renaming for ordinary path semantics.
    resolved=resolve_paths(graphs);order,previous,deps=execution_plan(graphs,selected,resolved);hashes={'source':'source'}
    for op in order:
        params={k:v for k,v in op.params.items() if k!='pipeline_ids'}
        hashes[op.id]=hashlib.sha256(json.dumps([op.kind,params,hashes[previous[op.id]],[hashes[d] for d in deps[op.id]]],sort_keys=True).encode()).hexdigest()
    return json.dumps([hashes[resolved[selected][-1].id],sorted(hashes[op.id] for op in order)])

def score(frame,sample):
    detections=frame.details.get('detections',[]);truth=[[b.x,b.y,b.width,b.height] for b in sample.boxes]
    pairs=sorted([(iou(d['normalized_box'],b),i,j) for i,d in enumerate(detections) for j,b in enumerate(truth) if iou(d['normalized_box'],b)>=.5],reverse=True)
    found=set();used=set();overlaps=[];matched_overlaps={}
    for overlap,i,j in pairs:
        if i not in used and j not in found:used.add(i);found.add(j);overlaps.append(overlap);matched_overlaps[str(j)]=overlap
    return {'sample_id':sample.id,'name':sample.name,'tp':len(found),'fp':len(detections)-len(found),'fn':len(truth)-len(found),'matched_targets':sorted(found),'matched_overlaps':matched_overlaps,'mean_iou':statistics.mean(overlaps) if overlaps else None,'count':len(detections),'measurement_basis':frame.details.get('measurement_basis','')}

def aggregate(rows):
    tp=sum(r['tp'] for r in rows);fp=sum(r['fp'] for r in rows);fn=sum(r['fn'] for r in rows)
    overlap=sum(sum(r.get('matched_overlaps',{}).values()) for r in rows)
    return {'tp':tp,'fp':fp,'fn':fn,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,'localization_iou':overlap/(tp+fn) if tp+fn else None}

def no_regression(rows,baseline):
    return len(rows)==len(baseline) and all(set(a['matched_targets'])>=set(b['matched_targets']) and a['fp']<=b['fp'] and all(a.get('matched_overlaps',{}).get(str(i),0)>=b.get('matched_overlaps',{}).get(str(i),0)-.02 for i in b['matched_targets']) for a,b in zip(rows,baseline))

def neighbors(candidate):
    graphs=candidate['graphs'];selected=candidate['selected'];order=execution_plan(graphs,selected)[0]
    changes=[]
    # Interleave operations so a long HSV schema does not consume the whole search.
    for op in order:
        options=[];p=op.params
        for field in ('value','low','high','hue_low','hue_high','saturation_low','value_low','constant','kernel','min_area','min_pixels','min_circularity','votes','gamma'):
            if field not in p:continue
            value=p[field]
            if field in ('min_area','min_pixels'):values=[value*.5,value*2]
            elif field=='min_circularity':values=[max(0,value-.15),min(1,value+.15)]
            elif field=='kernel':values=[max(1,value-2),value+2]
            elif field=='gamma':values=[max(.1,value-.25),min(5,value+.25)]
            else:
                delta=2 if field in ('hue_low','hue_high','constant') else 15 if field not in ('votes',) else 5
                values=[value-delta,value+delta]
            for v in values:
                if isinstance(value,int):v=int(round(v))
                options.append((op.id,field,v))
        # Kernel=1 preserves IDs and branches while making blur/morph no-ops.
        if op.kind in ('gaussian_blur','median_blur','morph_open','morph_close','erode','dilate') and p['kernel']!=1:options.insert(0,(op.id,'kernel',1))
        changes.append(options)
    for index in range(max(map(len,changes),default=0)):
        for options in changes:
            if index>=len(options):continue
            oid,key,value=options[index];next_graph=copy.deepcopy(graphs)
            try:
                for t in next_graph:
                    for j,op in enumerate(t.operations):
                        if op.id==oid:t.operations[j]=type(op).model_validate({**op.model_dump(),'params':{**op.params,key:value}})
                validate_export_graph(SimpleNamespace(timelines=next_graph,selected_timeline_id=selected))
                yield {'graphs':next_graph,'selected':selected,'name':f'{candidate["name"]} · {key} {value}','changes':candidate['changes']+[{'operation':oid,'parameter':key,'value':value}]}
            except ValueError:continue

def optimize(request,cancel_event=None):
    start=time.monotonic();deadline=start+request.budget_seconds
    samples=[s for s in request.samples if s.split=='train']
    baseline={'graphs':compact_graph(request.timelines,request.selected_timeline_id),'selected':request.selected_timeline_id,'name':'Current pipeline','changes':[],'rows':[],'errors':[]}
    all_candidates=[baseline];seen={signature(baseline['graphs'],baseline['selected'])};counts={'executed_nodes':0,'cache_hits':0,'cache_peak_bytes':0};stopped='candidate limit'
    def append(candidate):
        key=signature(candidate['graphs'],candidate['selected'])
        if key in seen:return False
        seen.add(key);candidate.update(rows=[],errors=[]);all_candidates.append(candidate);return True
    for seed in request.seeds:
        append({'graphs':compact_graph(seed.timelines,seed.selected_timeline_id),'selected':seed.selected_timeline_id,'name':seed.name,'changes':[{'proposal':'Suggested structure'}]})
    first_limit=max(len(all_candidates),request.max_trials//2)
    for candidate in neighbors(baseline):
        if len(all_candidates)>=first_limit:break
        append(candidate)
    pixels=0
    for sample in samples:
        check_cancelled(cancel_event);source=decode_image(sample.data);pixels+=source.shape[0]*source.shape[1]
        if pixels>40_000_000:raise ValueError('The training family exceeds 40 megapixels.')
        try:
            final,elapsed=execute(source,baseline['graphs'],baseline['selected'],request.measurements,cancel_event=cancel_event,deadline=deadline)
            row=score(final,sample);row['screen_ms']=elapsed;baseline['rows'].append(row)
            counts['executed_nodes']+=len(execution_plan(baseline['graphs'],baseline['selected'])[0])
        except SearchDeadline:raise ValueError('The search budget ended before the baseline was evaluated. Increase the budget or reduce image size.')
        except (ValueError,cv2.error) as error:raise ValueError(f'The current pipeline failed on {sample.name}. Fix its inputs before optimization: {str(error)[:200]}') from error
    tested=1
    for round_index in range(2):
        batch=all_candidates[tested:]
        if not batch:stopped='search space exhausted';break
        try:
            for sample in samples:
                check_cancelled(cancel_event);source=decode_image(sample.data);cache=FrameCache()
                for candidate in batch:
                    try:
                        final,elapsed=execute(source,candidate['graphs'],candidate['selected'],request.measurements,cache,cancel_event,deadline)
                        row=score(final,sample);row['screen_ms']=elapsed;candidate['rows'].append(row)
                    except (ValueError,cv2.error) as error:candidate['errors'].append({'sample_id':sample.id,'error':str(error)[:240]})
                counts['executed_nodes']+=cache.executed;counts['cache_hits']+=cache.hits;counts['cache_peak_bytes']=max(counts['cache_peak_bytes'],cache.peak)
        except SearchDeadline:stopped='time budget';break
        tested=len(all_candidates)
        if baseline['errors'] or len(baseline['rows'])!=len(samples):raise ValueError('The current pipeline failed on training images. Fix its inputs before optimization.')
        if round_index==0:
            ranked=sorted([c for c in all_candidates if len(c['rows'])==len(samples) and not c['errors']],key=lambda c:(-(aggregate(c['rows'])['f1'] or 0),-(aggregate(c['rows'])['localization_iou'] or 0),sum(r['screen_ms'] for r in c['rows'])))[:3]
            iterators=[iter(neighbors(c)) for c in ranked]
            while iterators and len(all_candidates)<request.max_trials:
                for iterator in iterators[:]:
                    try:
                        if len(all_candidates)<request.max_trials:append(next(iterator))
                    except StopIteration:iterators.remove(iterator)
    if baseline['errors'] or len(baseline['rows'])!=len(samples):raise ValueError('The search budget ended before the baseline was evaluated. Increase the budget or reduce image size.')
    complete=[c for c in all_candidates if not c['errors'] and len(c['rows'])==len(samples)]
    for c in complete:c['metrics']=aggregate(c['rows']);c['eligible']=no_regression(c['rows'],baseline['rows'])
    pool=[c for c in complete if c is not baseline and c['eligible']]
    speed=lambda c:sum(r['screen_ms'] for r in c['rows'])
    quality=lambda c:(-(c['metrics']['f1'] or 0),-(c['metrics']['localization_iou'] or 0),speed(c))
    eligible=[]
    if pool:
        for c in [min(pool,key=quality),min(pool,key=speed),*sorted(pool,key=quality)]:
            if not any(c is existing for existing in eligible):eligible.append(c)
            if len(eligible)==3:break
    finalists=[baseline,*eligible]
    # Fresh uncached timing: the search cache does not make deployment work free.
    for candidate in finalists:candidate['durations']=[];candidate['image_times']={s.id:[] for s in samples};candidate['preview']=None
    benchmark_deadline=time.monotonic()+min(10,request.budget_seconds);timing_incomplete=False
    try:
        for si,sample in enumerate(samples):
            source=decode_image(sample.data)
            for repeat in range(4):
                order=finalists if repeat%2==0 else list(reversed(finalists))
                for c in order:
                    check_cancelled(cancel_event)
                    final,elapsed=execute(source,c['graphs'],c['selected'],request.measurements,cancel_event=cancel_event,deadline=benchmark_deadline)
                    if repeat:c['durations'].append(elapsed);c['image_times'][sample.id].append(elapsed)
                    if si==0 and c['preview'] is None:c['preview']=preview_url(final.preview if final.preview is not None else final.image)
    except SearchDeadline:timing_incomplete=True
    timed=lambda c:all(len(values)==3 for values in c['image_times'].values())
    result=[];base_time=statistics.median(baseline['durations']) if timed(baseline) else None
    for i,c in enumerate(finalists):
        median=statistics.median(c['durations']) if timed(c) else None;spread=[min(c['durations']),max(c['durations'])] if timed(c) else None
        changed_basis=any(a['measurement_basis']!=b['measurement_basis'] for a,b in zip(c['rows'],baseline['rows']))
        localization_gain=(c['metrics']['localization_iou'] or 0)>=(baseline['metrics']['localization_iou'] or 0)+.03
        quality_gain=c['metrics']['tp']>baseline['metrics']['tp'] or c['metrics']['fp']<baseline['metrics']['fp'] or localization_gain
        clear_speed=bool(median is not None and base_time is not None and median<base_time*.9 and all(max(c['image_times'][s.id])<min(baseline['image_times'][s.id]) for s in samples))
        result.append({'id':f'candidate-{i}','name':c['name'],'baseline':i==0,'recommended':i>0 and c['eligible'] and not changed_basis and (quality_gain or clear_speed),
            'timelines':[t.model_dump() for t in c['graphs']],'selected_timeline_id':c['selected'],'changes':c['changes'],'metrics':c['metrics'],'per_image':c['rows'],
            'no_training_regression':c['eligible'],'localization_improved':localization_gain,'measurement_method_changed':changed_basis,'local_ms':median,'local_range_ms':spread,'timing_per_image':{key:{'median_ms':statistics.median(values),'range_ms':[min(values),max(values)],'repeats':len(values)} for key,values in c['image_times'].items() if values},'target':estimate_ms(median,request.hardware) if median is not None else None,'preview':c['preview']})
    return {'candidates':result,'evaluated':len(complete),'attempted':len(all_candidates),'failed_or_incomplete':len(all_candidates)-len(complete),'stopped':stopped,'wall_ms':(time.monotonic()-start)*1000,'timing_incomplete':timing_incomplete,**counts,
        'timing_note':'Search executes each uncached node once without PNG encoding. Finalists use one warmup and 3 fresh runs per training image; no cached timing shortcuts. Final timing has an additional budget of at most 10 seconds. Incomplete timing stays unknown. Deadlines stop between native calls.',
        'limitations':['Training box scores are not held-out reliability, mask quality, physical measurement accuracy or barcode identity accuracy.','Eligible alternatives retain baseline-matched targets, do not increase false-positive counts on any training image, and lose at most 0.02 IoU per matched target.','Baseline stays unchanged. Add an alternative explicitly, then test it on fresh held-out images.']}
