import test from 'node:test';
import assert from 'node:assert/strict';
import {aggregate,inputKind,estimate,normalizedBox} from '../static/evaluation.mjs';
test('training and validation metrics remain separate with explicit unlabeled coverage',()=>{
  const samples=[{id:'a',split:'train',labeled:true,boxes:[{}]},{id:'b',split:'validation',labeled:true,boxes:[{}]},{id:'c',split:'validation',labeled:false,boxes:[]}];
  const image=fit=>({timelines:[{id:'t',errors:0,path:['last'],local_ms:2}],stages:{last:{details:{fit}}}});
  const results=new Map([['a',image({tp:1,fp:0,fn:0})],['b',image({tp:0,fp:2,fn:1})],['c',image(null)]]);
  assert.equal(aggregate('t',samples,results,'train').f1,1);
  const val=aggregate('t',samples,results,'validation');assert.equal(val.f1,0);assert.equal(val.labeled,1);assert.equal(val.total,2);assert.equal(val.tested,2);
});
test('negative-only success never fabricates a numeric F1',()=>{
  const result=new Map([['n',{timelines:[{id:'t',errors:0,path:['x'],local_ms:1}],stages:{x:{details:{fit:{tp:0,fp:0,fn:0}}}}}]]);
  const stats=aggregate('t',[{id:'n',split:'validation',labeled:true,boxes:[]}],result,'validation');assert.equal(stats.f1,null);assert.equal(stats.emptyCorrect,1);
});
test('operation picker infers actual upstream type including blurred masks',()=>{
  const catalog=[{kind:'hsv_mask',accepts:['color']},{kind:'gaussian_blur',accepts:['color','gray','mask']},{kind:'grayscale',accepts:['color']}];
  const path=[{kind:'hsv_mask',params:{}},{kind:'gaussian_blur',params:{kernel:3}}];
  assert.equal(inputKind(path,1,catalog),'mask');assert.equal(inputKind(path,2,catalog),'gray');
  assert.equal(inputKind([...path,{kind:'grayscale'}],3,catalog),null);
});
test('hardware re-estimation preserves measured timings and rejects unknown factors',()=>{
  assert.equal(estimate(4,{mode:'relative',relative_speed:.5}).ms,8);
  assert.equal(estimate(4,{mode:'clock',host_ghz:4,target_ghz:2}).high_ms,24);
  assert.equal(estimate(4,{mode:'clock',target_ghz:2}).ms,null);
});
test('failed, untested and unlabeled images remain visible in collection coverage',()=>{
  const samples=[{id:'bad',split:'validation',labeled:true,boxes:[{}]},{id:'pending',split:'validation',labeled:false,boxes:[]}];
  const results=new Map([['bad',{timelines:[{id:'t',errors:2,path:[],local_ms:null}],stages:{}}]]);
  const a=aggregate('t',samples,results,'validation');assert.equal(a.tested,1);assert.equal(a.failed,1);assert.equal(a.untested,1);assert.equal(a.unlabeled,1);assert.equal(a.labeled,0);assert.equal(a.f1,null);
});
test('drawn boxes handle reverse dragging, clamp to the image and reject clicks',()=>{
  assert.deepEqual(normalizedBox(.8,.7,.2,.1),{x:.2,y:.1,width:.6000000000000001,height:.6});
  assert.deepEqual(normalizedBox(-.2,.2,1.2,2),{x:0,y:.2,width:1,height:.8});
  assert.equal(normalizedBox(.1,.1,.101,.101),null);
});
