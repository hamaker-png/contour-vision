import test from 'node:test';
import assert from 'node:assert/strict';
import {reviewImage,matchedBoxes} from '../static/validation_review.mjs';
import {aggregate} from '../static/evaluation.mjs';
const sample={id:'a',split:'validation',labeled:true,boxes:[{}]};
const result={timelines:[{id:'t',path:['detect','invert'],errors:0,local_ms:2}],stages:{detect:{details:{detections:[{}],count:1,fit:{tp:1,fp:0,fn:0,f1:1}}},invert:{details:{}}}};
test('intermediate measurements cannot imply the final transform is a detector',()=>{
  const r=reviewImage('t',sample,result);assert.equal(r.status,'transform');assert.equal(r.measurementId,'detect');assert.equal(r.finalId,'invert');assert.match(r.summary,/earlier step/);
  assert.equal(aggregate('t',[sample],new Map([['a',result]]),'validation').labeled,0);
});
test('failed retry excludes previous good scores and exposes actual error',()=>{
  const image=structuredClone(result);image.timelines[0].path=['detect'];
  const r=reviewImage('t',sample,image,'Connection lost');assert.equal(r.status,'failed');assert.deepEqual(r.errors,['Connection lost']);
  const a=aggregate('t',[sample],new Map([['a',image]]),'validation',new Map([['a','Connection lost']]));
  assert.equal(a.failed,1);assert.equal(a.tested,1);assert.equal(a.labeled,0);assert.equal(a.f1,null);
});
test('negative and untested images have explicit states without manufactured F1',()=>{
  assert.equal(reviewImage('t',sample).status,'untested');
  const image=structuredClone(result);image.timelines[0].path=['detect'];image.stages.detect.details={detections:[],count:0,fit:{tp:0,fp:0,fn:0,f1:null}};
  const r=reviewImage('t',{...sample,boxes:[]},image);assert.equal(r.status,'negative');assert.equal(r.summary,'Negative image · 0 false detections');
});
test('box assignments expose missed and extra indices, with backend-compatible tie breaks',()=>{
  const s={labeled:true,boxes:[{x:0,y:0,width:.2,height:.2},{x:.5,y:.5,width:.2,height:.2}]};
  const detections=[{normalized_box:[0,0,.2,.2]},{normalized_box:[0,0,.2,.2]}];
  const match=matchedBoxes(s,detections,{tp:1,fp:1,fn:1});assert.deepEqual(match,{matches:[{detection:1,label:0}],extra:[0],missed:[1]});
  assert.equal(matchedBoxes(s,detections,{tp:2,fp:0,fn:0}),null);
});
