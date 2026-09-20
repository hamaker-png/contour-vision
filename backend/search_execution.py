"""Single-pass, no-encoding execution for bounded candidate search."""
from collections import OrderedDict,Counter
import hashlib,json,sys,time
import numpy as np
from .cpu_work import check_cancelled
from .timelines import Frame,apply_operation,execution_plan,resolve_paths
from .vision_params import supporting_ids
from .vision_ops import confirm_frame

def frame_bytes(frame):
    seen=set()
    def size(value):
        if id(value) in seen:return 0
        seen.add(id(value))
        if isinstance(value,np.ndarray):
            base=value
            while isinstance(base.base,np.ndarray):base=base.base
            if base is not value:return size(base)
            return base.nbytes+sys.getsizeof(base)
        if isinstance(value,dict):return sys.getsizeof(value)+sum(size(k)+size(v) for k,v in value.items())
        if isinstance(value,(list,tuple)):return sys.getsizeof(value)+sum(size(v) for v in value)
        return sys.getsizeof(value)
    return sum(size(getattr(frame,name)) for name in ('image','preview','details','regions'))

class FrameCache:
    def __init__(self,max_bytes=128*1024*1024):
        self.limit=max_bytes;self.bytes=0;self.peak=0;self.entries=OrderedDict();self.hits=0;self.executed=0;self.source_key=None;self.source=None
    def get(self,key):
        if key not in self.entries:return None
        self.entries.move_to_end(key);self.hits+=1
        return self.entries[key][:2]
    def put(self,key,frame,elapsed):
        size=frame_bytes(frame)
        if size>self.limit:return
        while self.entries and self.bytes+size>self.limit:
            _,(_,_,removed)=self.entries.popitem(last=False);self.bytes-=removed
        self.entries[key]=(frame,elapsed,size);self.bytes+=size;self.peak=max(self.peak,self.bytes)

class SearchDeadline(Exception):pass

def execute(source,graphs,selected,measurements,cache=None,cancel_event=None,deadline=None,trace=None,trace_ids=()):
    resolved=resolve_paths(graphs);order,previous,deps=execution_plan(graphs,selected,resolved)
    final=resolved[selected][-1].id
    frames={'source':Frame(source,'color')};semantic={}
    if cache:
        if cache.source is not source:
            cache.entries.clear();cache.bytes=0;cache.source=source
            digest=hashlib.sha256(memoryview(np.ascontiguousarray(source)).cast('B'));digest.update(str(source.shape).encode());cache.source_key=digest.hexdigest()
        semantic['source']=cache.source_key
    # Unselected workspace branches never consume their inputs in this execution.
    remaining=Counter(node for op in order for node in deps[op.id])
    elapsed=0;configuration=measurements.model_dump()
    for op in order:
        check_cancelled(cancel_event)
        if deadline and time.monotonic()>deadline:raise SearchDeadline()
        key=hashlib.sha256(json.dumps([op.kind,op.params,semantic.get(previous[op.id]),[semantic[d] for d in deps[op.id]],configuration],sort_keys=True,separators=(',',':')).encode()).hexdigest() if cache else None
        hit=cache.get(key) if cache else None
        if hit:frame,duration=hit
        else:
            start=time.perf_counter_ns()
            if op.kind=='confirm':
                supports=[(tid,frames[resolved[tid][-1].id]) for tid in supporting_ids(op)]
                frame=confirm_frame(frames[previous[op.id]],supports,op.params,source,measurements)
            else:frame=apply_operation(frames[previous[op.id]],op,source,measurements)
            duration=(time.perf_counter_ns()-start)/1e6
            if cache:cache.executed+=1;cache.put(key,frame,duration)
        frames[op.id]=frame;semantic[op.id]=key;elapsed+=duration
        if trace is not None and op.id in trace_ids:trace[op.id]=(frame,duration)
        for node in deps[op.id]:
            remaining[node]-=1
            if remaining[node]==0 and node!='source':frames.pop(node,None)
        check_cancelled(cancel_event)
    return frames[final],elapsed
