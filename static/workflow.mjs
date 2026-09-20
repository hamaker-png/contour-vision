export const clone = value => structuredClone(value);
export const uid = prefix => `${prefix}_${crypto.randomUUID().replaceAll('-', '').slice(0, 16)}`;
export function paths(timelines) {
  const byId = new Map(timelines.map(t => [t.id, t]));
  if (byId.size !== timelines.length) throw Error('Pipeline IDs must be unique.');
  const ids = timelines.flatMap(t => t.operations.map(o => o.id));
  if (new Set(ids).size !== ids.length || ids.includes('source')) throw Error('Operation IDs must be unique.');
  if (timelines.length > 8 || ids.length > 64) throw Error('Use at most 8 pipelines and 64 operations.');
  const done = new Map(), visiting = new Set();
  function resolve(id) {
    if (done.has(id)) return done.get(id);
    if (visiting.has(id)) throw Error('Branches cannot form a cycle.');
    const t = byId.get(id);
    if (!t) throw Error('A parent pipeline is missing.');
    if (t.operations.length > 12) throw Error('Use at most 12 new operations per pipeline.');
    visiting.add(id);
    let prefix = [];
    if (t.parent_id !== null) {
      const parent = resolve(t.parent_id), i = parent.findIndex(o => o.id === t.fork_after);
      if (t.fork_after !== 'source' && i < 0) throw Error('This edit would remove a branch point. Reconnect or remove its dependent branch first.');
      prefix = t.fork_after === 'source' ? [] : parent.slice(0, i + 1);
    } else if (t.fork_after !== null) throw Error('A root pipeline cannot have a fork point.');
    const path = [...prefix, ...t.operations];
    if (path.length > 20) throw Error('Use at most 20 operations in a complete path.');
    done.set(id, path); visiting.delete(id); return path;
  }
  timelines.forEach(t => resolve(t.id));
  const previous=new Map(),nodes=new Map();
  for(const path of done.values()){let prior=null;for(const op of path){previous.set(op.id,prior);nodes.set(op.id,op);prior=op.id;}}
  const checked=new Set(),checking=new Set();
  function check(id){
    if(!id||checked.has(id))return;
    if(checking.has(id))throw Error('Pipeline branches and confirmation cannot form a cycle.');
    checking.add(id);check(previous.get(id));
    const finalIds=new Set();
    for(const reference of supportingIds(nodes.get(id))){
      if(!done.has(reference))throw Error('A supporting pipeline is missing. Reconnect confirmation before removing it.');
      const final=done.get(reference).at(-1);if(!final)throw Error('A supporting pipeline needs a detector first.');
      if(final.id===previous.get(id)||finalIds.has(final.id))throw Error('Confirmation needs distinct detector results. Aliases of the primary or another support do not add evidence.');
      finalIds.add(final.id);check(final.id);
    }
    checking.delete(id);checked.add(id);
  }
  for(const id of nodes.keys())check(id);
  return done;
}
export const supportingIds=op=>op?.kind==='confirm'?(op.params.pipeline_ids||'').split(',').map(s=>s.trim()).filter(Boolean):[];
export function dependencyIds(timelines,timelineId){
  const graph=paths(timelines),seen=new Set();
  function visit(path){for(const op of path){if(seen.has(op.id))continue;for(const ref of supportingIds(op))visit(graph.get(ref));seen.add(op.id);}}
  visit(graph.get(timelineId)||[]);return seen;
}
export function editGraph(timelines, edit) {
  const next = clone(timelines); edit(next); paths(next); return next;
}
export function moveOperation(timelines, timelineId, operationId, index) {
  return editGraph(timelines, next => {
    const t = next.find(t => t.id === timelineId), from = t.operations.findIndex(o => o.id === operationId);
    if (from < 0) throw Error('Shared steps are edited in their original pipeline.');
    const [operation] = t.operations.splice(from, 1);
    t.operations.splice(Math.max(0, Math.min(index, t.operations.length)), 0, operation);
  });
}
export function remapDraft(timelines, prefix = uid('draft')) {
  prefix = prefix.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 60) || 'draft';
  const next = clone(timelines), timelineIds = new Map(next.map((t,i) => [t.id, `${prefix}_t${i}`]));
  const nodeIds = new Map(next.flatMap(t => t.operations).map((o,i) => [o.id, `${prefix}_n${i}`]));
  for (const t of next) {
    t.id = timelineIds.get(t.id); t.parent_id = t.parent_id === null ? null : timelineIds.get(t.parent_id);
    t.fork_after = t.fork_after === null || t.fork_after === 'source' ? t.fork_after : nodeIds.get(t.fork_after);
    t.operations.forEach(o => { o.id = nodeIds.get(o.id);if(o.kind==='confirm')o.params.pipeline_ids=supportingIds(o).map(id=>timelineIds.get(id)||id).join(','); });
  }
  paths(next); return next;
}
export function formatMs(value) {
  if (value === null || value === undefined) return '—';
  if (value > 0 && value < .001) return '<0.001';
  return Number(value).toFixed(value < 1 ? 3 : 2);
}
export function orderedTimelines(timelines) {
  const result = [], visited = new Set();
  function visit(t) {
    if (visited.has(t.id)) return;
    visited.add(t.id); result.push(t); timelines.filter(child => child.parent_id === t.id).forEach(visit);
  }
  timelines.filter(t => t.parent_id === null).forEach(visit); return result;
}
export class Revision {
  value = 0;
  bump() { return ++this.value; }
  current(value) { return value === this.value; }
}

export function validSelection(timelines, selection) {
  const graph = paths(timelines);
  if (!selection || !graph.has(selection.timeline)) return timelines[0] ? {timeline:timelines[0].id,node:'source'} : null;
  return selection.node === 'source' || graph.get(selection.timeline).some(o=>o.id===selection.node) ? selection : {timeline:selection.timeline,node:'source'};
}

export function savedSelection(timelines, selection, recommendedTimeline) {
  const graph=paths(timelines);
  if(selection && typeof selection.timeline==='string' && graph.has(selection.timeline)) {
    return validSelection(timelines,{timeline:selection.timeline,node:typeof selection.node==='string'?selection.node:'source'});
  }
  if(typeof recommendedTimeline==='string' && graph.has(recommendedTimeline)) {
    return {timeline:recommendedTimeline,node:graph.get(recommendedTimeline).at(-1)?.id||'source'};
  }
  return validSelection(timelines,null);
}
