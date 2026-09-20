import test from 'node:test';
import assert from 'node:assert/strict';
import {AISession} from '../static/ai_session.mjs';

test('new AI request aborts the old request and rejects late results',()=>{
  const session=new AISession(),old=session.start({samples:['A']}),latest=session.start({samples:['B']});
  assert.equal(old.signal.aborted,true);assert.equal(session.current(old,{samples:['A']}),false);
  assert.equal(session.current(latest,{samples:['B']}),true);
});
test('changed image labels, model or target invalidate an otherwise completed suggestion',()=>{
  const body={model:'model-a',description:'red',samples:[{id:'one',split:'train',boxes:[]}]};
  const session=new AISession(),ticket=session.start(body);
  for(const change of [{...body,model:'model-b'},{...body,description:'blue'},{...body,samples:[{...body.samples[0],boxes:[{x:0}]}]}])assert.equal(session.current(ticket,change),false);
  session.cancel();assert.equal(ticket.signal.aborted,true);assert.equal(session.current(ticket,body),false);
});
