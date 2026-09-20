import test from 'node:test';
import assert from 'node:assert/strict';
import {updateAnswer,formatAnswers,checkedAnswers,familyFingerprint,readGuidance} from '../static/clarifications.mjs';

test('new discovery questions do not erase previously answered constraints',()=>{
  let answers=updateAnswer([],'Which shape?','Round');
  answers=updateAnswer(answers,'Which dimension?','Length');
  answers=updateAnswer(answers,'Which shape?','Round or oval');
  assert.equal(answers.length,2);
  assert.equal(formatAnswers(answers,'Reject orange objects'),'Which dimension?: Length\nWhich shape?: Round or oval\nReject orange objects');
  assert.equal(updateAnswer(answers,'Which shape?','').length,1);
});

test('combined answer budget rejects overflow without truncation',()=>{
  const answers=[{question:'Shape',answer:'x'.repeat(5993)}];
  assert.equal(checkedAnswers(answers).length,6000);
  assert.throws(()=>checkedAnswers(answers,'Do not ignore this'),/nothing has been discarded/);
});

test('saved discovery binds to the training family including labels, not held-out images',async()=>{
  const sample={id:'a',name:'a.png',data:'pixels',labeled:false,boxes:[],split:'train'};
  const fingerprint=await familyFingerprint([sample]);
  assert.equal(fingerprint,await familyFingerprint([sample,{...sample,id:'b',split:'validation'}]));
  assert.notEqual(fingerprint,await familyFingerprint([{...sample,labeled:true}]));
  const guidance={answers:[{question:'Shape?',answer:'Round'}],discovery:{observations:'Two circles',important_features:['Round'],questions:['Shape?'],limitations:[],imageCount:1,familyFingerprint:fingerprint}};
  assert.deepEqual(readGuidance(JSON.parse(JSON.stringify(guidance))),guidance);
  assert.throws(()=>readGuidance({...guidance,discovery:{...guidance.discovery,familyFingerprint:'bad'}}),/invalid/);
});

test('many short historical answers and over-budget drafts remain reopenable for editing',()=>{
  const answers=Array.from({length:48},(_,i)=>({question:`Question ${i}`,answer:'Yes'}));
  answers.push({question:'Long draft',answer:'x'.repeat(7000)});
  assert.deepEqual(readGuidance({answers,discovery:null}).answers,answers);
  assert.throws(()=>checkedAnswers(answers),/Shorten them/);
});
