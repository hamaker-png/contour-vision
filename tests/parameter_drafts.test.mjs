import test from 'node:test';
import assert from 'node:assert/strict';
import {ParameterDrafts} from '../static/parameter_drafts.mjs';
test('drafts retain empty number text and booleans without changing committed parameters',()=>{
  const d=new ParameterDrafts(),op={id:'a',kind:'test',params:{threshold:10,invert:false}};
  d.record(op,{threshold:'',invert:true});assert.deepEqual(d.read(op),{threshold:'',invert:true});assert.deepEqual(op.params,{threshold:10,invert:false});
  d.record(op,{threshold:'10',invert:false});assert.equal(d.size,0);
});
test('selection and image navigation retain drafts; changed or removed operations discard them',()=>{
  const d=new ParameterDrafts(),op={id:'a',kind:'resize',params:{max_side:1280}};
  d.record(op,{max_side:'640'});d.reconcile([{operations:[structuredClone(op)]}]);assert.equal(d.read(op).max_side,'640');
  d.reconcile([{operations:[{...op,params:{max_side:800}}]}]);assert.equal(d.size,0);
  d.record(op,{max_side:'640'});d.reconcile([]);assert.equal(d.size,0);
});
