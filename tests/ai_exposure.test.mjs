import test from 'node:test';
import assert from 'node:assert/strict';
import {ExposureLedger} from '../static/ai_exposure.mjs';

test('submitted training image stays exposed through role changes, reupload and older project imports',async()=>{
  const image={id:'one',data:'same image bytes',split:'train'},ledger=new ExposureLedger();
  await ledger.prepare([image]);const old=ledger.save();
  assert.equal(ledger.status(image),'unseen');
  ledger.markSubmitted([image]);
  const uploadedAgain={...image,id:'new-id',split:'validation'};await ledger.prepare([uploadedAgain]);
  ledger.merge(old,[uploadedAgain]);
  assert.equal(ledger.status(uploadedAgain),'submitted');
  const restored=new ExposureLedger();await restored.prepare([uploadedAgain]);restored.merge(ledger.save(),[uploadedAgain]);
  assert.equal(restored.status(uploadedAgain),'submitted');
});

test('held-out inputs are never marked submitted; legacy projects have unknown exposure',async()=>{
  const held={id:'held',data:'heldout pixels',split:'validation'},ledger=new ExposureLedger();
  await ledger.prepare([held]);ledger.markSubmitted([held]);assert.equal(ledger.status(held),'unseen');
  ledger.merge(null,[held]);assert.equal(ledger.status(held),'unknown');
  assert.throws(()=>ledger.merge({version:1,submitted:['bad'],unknown:[]},[held]),/invalid/);
});

for(const history of ['submitted','tuned','unknown'])test(`encoded-only ${history} migrates to identical decoded pixels`,async()=>{
  const a={data:'PNG encoding A',split:'train'},b={data:'PNG encoding B',split:'validation'};
  const old=new ExposureLedger(async()=>null);await old.prepare([a]);
  if(history==='unknown')old.merge(null,[a]);else old[history==='tuned'?'markTuned':'markSubmitted']([a]);
  const migrated=new ExposureLedger(async()=>'a'.repeat(64));await migrated.prepare([a]);migrated.merge(old.save(),[a]);
  migrated.retain([]);await migrated.prepare([b]);assert.equal(migrated.status(b),history);
  assert.equal(migrated.keys.size,1);
});

test('failed preparation retries and concurrent families decode one image at a time',async()=>{
  let attempts=0,active=0,maximum=0;
  const ledger=new ExposureLedger(async()=>{attempts++;if(attempts===1)throw Error('decode failure');active++;maximum=Math.max(maximum,active);await new Promise(resolve=>setTimeout(resolve,5));active--;return null;});
  const a={data:'one',split:'train'},b={data:'two',split:'train'};
  await assert.rejects(ledger.prepare([a]),/decode failure/);
  await Promise.all([ledger.prepare([a]),ledger.prepare([b])]);
  assert.equal(attempts,3);assert.equal(maximum,1);assert.equal(ledger.pending.size,0);
  ledger.markTuned([a,b]);ledger.retain([]);await ledger.prepare([a]);assert.equal(ledger.status(a),'tuned');
});
