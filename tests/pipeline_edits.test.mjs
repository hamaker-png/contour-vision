import test from 'node:test';
import assert from 'node:assert/strict';
import {typeIssues,previewMove,gapIndex,independentCopy} from '../static/pipeline_edits.mjs';
import {paths} from '../static/workflow.mjs';
const catalog=[{kind:'resize',name:'Resize',accepts:['color','gray','mask']},{kind:'gaussian_blur',name:'Blur',accepts:['color','gray','mask']},{kind:'hsv_mask',name:'HSV mask',accepts:['color']},{kind:'grayscale',name:'Grayscale',accepts:['color']},{kind:'canny',name:'Edges',accepts:['gray','mask']},{kind:'morph_open',name:'Open',accepts:['gray','mask']},{kind:'morph_close',name:'Close',accepts:['gray','mask']}];
const graph=()=>[
 {id:'main',name:'Color',parent_id:null,fork_after:null,operations:[{id:'r',kind:'resize',params:{}},{id:'b',kind:'gaussian_blur',params:{kernel:3}},{id:'h',kind:'hsv_mask',params:{}},{id:'o',kind:'morph_open',params:{}},{id:'c',kind:'morph_close',params:{}}]},
 {id:'branch',name:'Shape',parent_id:'main',fork_after:'b',operations:[{id:'g',kind:'grayscale',params:{}},{id:'e',kind:'canny',params:{}}]}
];
test('moving a color mask into a shared prefix is rejected before it breaks a dependent path',()=>{
 const before=graph();const preview=previewMove(before,'main','h',1,catalog);
 assert.equal(preview.allowed,false);assert.match(preview.reason,/needs/);assert.equal(preview.affected[0].id,'branch');
 assert.deepEqual(before[0].operations.map(o=>o.id),['r','b','h','o','c']);
});
test('valid morphology reorder changes exact order and has no unrelated branch impact',()=>{
 const preview=previewMove(graph(),'main','o',4,catalog);
 assert.equal(preview.allowed,true);assert.deepEqual(preview.next[0].operations.map(o=>o.id),['r','b','h','c','o']);assert.deepEqual(preview.affected,[]);
});
test('gap insertion accounts for removing the source before a later gap',()=>{
 assert.equal(gapIndex(1,4),3);assert.equal(gapIndex(3,1),1);assert.equal(gapIndex(1,2),1);assert.equal(gapIndex(1,1),1);
});
test('shared nodes cannot move locally and independent copy isolates inherited steps',()=>{
 const before=graph();assert.equal(previewMove(before,'branch','b',0,catalog).allowed,false);
 const copy=independentCopy(before,'branch'),timeline=copy.timelines.at(-1);
 assert.equal(timeline.parent_id,null);assert.deepEqual(timeline.operations.map(o=>o.kind),['resize','gaussian_blur','grayscale','canny']);
 assert.ok(timeline.operations.every(o=>!paths(before).get('branch').some(old=>old.id===o.id)));
 timeline.operations[1].params.kernel=7;assert.equal(before[0].operations[1].params.kernel,3);
});
test('mask blur changing to gray is visible to type validation',()=>{
 const value=graph();value[0].operations.push({id:'gray',kind:'grayscale',params:{}});
 assert.equal(typeIssues(value,catalog)[0].input,'mask');
});
