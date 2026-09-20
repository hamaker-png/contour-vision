import test from 'node:test';
import assert from 'node:assert/strict';
import {paths,moveOperation,editGraph,remapDraft,orderedTimelines,validSelection,savedSelection,Revision} from '../static/workflow.mjs';
const graph=()=>[
  {id:'main',name:'Main',parent_id:null,fork_after:null,operations:[{id:'resize',kind:'resize'},{id:'blur',kind:'gaussian_blur'},{id:'hsv',kind:'hsv_mask'}]},
  {id:'branch',name:'Branch',parent_id:'main',fork_after:'blur',operations:[{id:'gray',kind:'grayscale'},{id:'edge',kind:'canny'}]},
];
test('reorder is immutable and stable fork ID follows the changed prefix',()=>{
  const before=graph(), after=moveOperation(before,'main','hsv',1);
  assert.deepEqual(paths(after).get('branch').map(o=>o.id),['resize','hsv','blur','gray','edge']);
  assert.deepEqual(before[0].operations.map(o=>o.id),['resize','blur','hsv']);
});
test('branch suffix moves independently; shared nodes must be edited in parent',()=>{
  const moved=moveOperation(graph(),'branch','edge',0);
  assert.deepEqual(paths(moved).get('branch').map(o=>o.id),['resize','blur','edge','gray']);
  assert.throws(()=>moveOperation(graph(),'branch','blur',0),/Shared steps/);
});
test('deleting a live fork cannot silently rewire a branch',()=>{
  assert.throws(()=>editGraph(graph(),next=>next[0].operations.splice(1,1)),/branch point/);
});
test('cycles and missing parents are rejected',()=>{
  assert.throws(()=>editGraph(graph(),next=>{next[0].parent_id='branch';next[0].fork_after='source';}),/cycle/);
  assert.throws(()=>editGraph(graph(),next=>next.shift()),/missing/);
});
test('AI draft merge remaps both operations and branch references',()=>{
  const draft=remapDraft(graph(),'unique');
  assert.deepEqual(paths([...graph(),...draft]).get('unique_t1').map(o=>o.id),['unique_n0','unique_n1','unique_n3','unique_n4']);
});
test('nested branches render under parents regardless of array order',()=>{
  const before=graph(); before.push({id:'child',name:'Child',parent_id:'branch',fork_after:'edge',operations:[]});
  assert.deepEqual(orderedTimelines(before.reverse()).map(t=>t.id),['main','branch','child']);
});
test('stale async responses cannot replace a newer revision',()=>{
  const revision=new Revision(), request=revision.bump(); revision.bump();
  assert.equal(revision.current(request),false); assert.equal(revision.current(revision.value),true);
});
test('reconnecting an earlier fork clears selection of excluded shared steps',()=>{
  const next=graph(); next[1].fork_after='resize';
  assert.deepEqual(validSelection(next,{timeline:'branch',node:'blur'}),{timeline:'branch',node:'source'});
  assert.deepEqual(validSelection(next,{timeline:'branch',node:'edge'}),{timeline:'branch',node:'edge'});
});
test('long model-generated IDs get short, unique replacements',()=>{
  const next=graph(); next[0].id='x'.repeat(100);next[1].parent_id=next[0].id;
  const draft=remapDraft(next,'prefix'); assert.ok(draft.every(t=>t.id.length<100));
  assert.equal(paths(draft).size,2);
});

test('saved projects restore the chosen branch instead of the first baseline',()=>{
  assert.deepEqual(savedSelection(graph(),{timeline:'branch',node:'edge'},'main'),{timeline:'branch',node:'edge'});
  assert.deepEqual(savedSelection(graph(),{timeline:'branch',node:'blur'}),{timeline:'branch',node:'blur'});
});
test('ready-made projects open their recommended final step through inherited paths',()=>{
  assert.deepEqual(savedSelection(graph(),undefined,'branch'),{timeline:'branch',node:'edge'});
  const copy=graph();copy[1].operations=[];
  assert.deepEqual(savedSelection(copy,undefined,'branch'),{timeline:'branch',node:'blur'});
});
test('stale saved selections and old image-only projects fall back safely',()=>{
  assert.deepEqual(savedSelection(graph(),{timeline:'removed',node:'edge'},'branch'),{timeline:'branch',node:'edge'});
  assert.deepEqual(savedSelection(graph(),{timeline:'branch',node:'removed'}),{timeline:'branch',node:'source'});
  assert.deepEqual(savedSelection(graph(),null,'missing'),{timeline:'main',node:'source'});
  assert.equal(savedSelection([],undefined,'missing'),null);
});
