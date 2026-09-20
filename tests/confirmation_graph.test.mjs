import test from 'node:test';
import assert from 'node:assert/strict';
import {paths,remapDraft,dependencyIds} from '../static/workflow.mjs';
import {typeIssues,previewMove,independentCopy} from '../static/pipeline_edits.mjs';
const graph=()=>[
 {id:'a',name:'Primary',parent_id:null,fork_after:null,operations:[{id:'r',kind:'resize',params:{}},{id:'m',kind:'hsv_mask',params:{}},{id:'d',kind:'contours',params:{}},{id:'c',kind:'confirm',params:{pipeline_ids:'b',min_support:1,iou:.3}}]},
 {id:'b',name:'Support',parent_id:'a',fork_after:'r',operations:[{id:'bm',kind:'hsv_mask',params:{}},{id:'bd',kind:'cimg_components',params:{}}]}
];
const catalog=[{kind:'resize',accepts:['color','gray','mask']},{kind:'hsv_mask',accepts:['color']},{kind:'contours',accepts:['mask'],detector:true},{kind:'cimg_components',accepts:['mask'],detector:true},{kind:'confirm',name:'Confirm',accepts:['mask'],detector:true},{kind:'invert',accepts:['mask','gray','color']}];
test('confirmation permits a support branch from an earlier shared step and costs each dependency once',()=>{
 assert.equal(paths(graph()).get('a').length,4);assert.deepEqual([...dependencyIds(graph(),'a')],['r','m','d','bm','bd','c']);assert.deepEqual(typeIssues(graph(),catalog),[]);
});
test('confirmation rejects genuine node cycles and deleted support',()=>{
 const g=graph();g[1].operations.push({id:'loop',kind:'confirm',params:{pipeline_ids:'a'}});assert.throws(()=>paths(g),/cycle/);assert.throws(()=>paths(graph().slice(0,1)),/supporting pipeline/);
});
test('AI remapping rewrites supporting pipeline IDs and retains acyclic topology',()=>{
 const g=remapDraft(graph(),'proposed');assert.equal(g[0].operations.at(-1).params.pipeline_ids,g[1].id);assert.equal(dependencyIds(g,g[0].id).size,6);
});
test('a transform after a supporting detector invalidates confirmation and its exact export',()=>{
 const g=graph();g[1].operations.push({id:'last',kind:'invert',params:{}});assert.equal(typeIssues(g,catalog)[0].operation,'c');assert.throws(()=>independentCopy(graph(),'a'),/confirms other branches/);
});
test('moving confirmation before its primary detector is blocked',()=>{
 assert.equal(previewMove(graph(),'a','c',2,catalog).allowed,false);
});
test('aliases of one detector cannot supply multiple confirmation votes',()=>{
 const g=graph();g.push({id:'alias',name:'Alias',parent_id:'a',fork_after:'d',operations:[]});g[0].operations.at(-1).params.pipeline_ids='alias';assert.throws(()=>paths(g),/distinct detector/);
});
test('move impact includes confirmation consumers',()=>{
 const g=graph();g[1].operations.splice(1,0,{id:'e',kind:'invert',params:{}},{id:'f',kind:'invert',params:{}});const result=previewMove(g,'b','e',2,catalog);assert.equal(result.allowed,true);assert.ok(result.affected.some(t=>t.id==='a'));assert.match(result.reason,/confirmation/);
});
