// Pauses real CPU HTTP requests in standalone Chrome; no AI provider fixtures.
import {connect} from './cdp.mjs';
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const p=await connect(JSON.parse(await readFile('artifacts/strict/root-tab.json')).id);
const requests=[],errors=[],networkFailures=[];let cursor=0;
p.on('Fetch.requestPaused',e=>requests.push(e));
p.on('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails.text));
p.on('Network.loadingFailed',e=>networkFailures.push(e));
async function next(){for(let n=0;n<100;n++){if(requests[cursor])return requests[cursor++];await new Promise(r=>setTimeout(r,100));}throw Error('No next CPU request');}
async function resume(e){await p.call('Fetch.continueRequest',{requestId:e.requestId});}
try{
  await p.call('Page.bringToFront');await p.call('Runtime.enable');await p.call('Network.enable');await p.call('Fetch.disable');
  await p.call('Emulation.setDeviceMetricsOverride',{width:1424,height:905,deviceScaleFactor:1,mobile:false});
  await p.call('Page.reload',{ignoreCache:true});await p.waitFor("document.querySelector('#status')?.textContent.includes('Add an image family')");
  await p.upload('#files',['smarties.png','horse.png','coins.png','red-apple.jpg','tennis-ball.png'].map(f=>resolve('examples',f)));
  await p.waitFor("document.querySelector('#image-count').textContent.startsWith('5 /')");
  await p.click('#manual-start');await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");
  await p.click('#close-inspector');await p.click('#auto-run');await p.click('#to-finish');
  const ids=await p.evaluate("[...document.querySelector('#validation-image').options].map(o=>o.value)");
  await p.call('Fetch.enable',{patterns:[{urlPattern:'*/api/timelines/run',requestStage:'Request'}]});
  await p.click('#validate-family');await resume(await next());
  const second=await next();
  await p.select('#validation-image',ids[4]);
  const navigating=await p.evaluate("({status:document.querySelector('#status').textContent,cancel:!document.querySelector('#cancel-run').hidden,summary:document.querySelector('#validation-summary').innerText})");
  await resume(second);const third=await next();await p.click('#cancel-run');
  const cancelled=await p.evaluate("({status:document.querySelector('#status').textContent,summary:document.querySelector('#validation-summary').innerText,continueVisible:!document.querySelector('#continue-run').hidden,cancelVisible:!document.querySelector('#cancel-run').hidden})");
  try{await resume(third);}catch{}await new Promise(r=>setTimeout(r,200));
  const oldAborted=networkFailures.some(e=>e.requestId===third.networkId&&e.canceled);
  await p.screenshot('artifacts/strict/round-08-cancel.png');
  await p.click('#continue-run');const remainingIds=[];
  for(let n=0;n<3;n++){const req=await next(),body=JSON.parse(req.request.postData);remainingIds.push(body.samples[0].id);await resume(req);}
  await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");
  const completed=await p.evaluate("({summary:document.querySelector('#validation-summary').innerText,continueHidden:document.querySelector('#continue-run').hidden,active:document.querySelector('#validation-image').value})");
  await p.click('#validate-family');const retried=await next();await p.click('#cancel-run');try{await resume(retried);}catch{}
  await new Promise(r=>setTimeout(r,200));
  const retryCancel=await p.evaluate("document.querySelector('#validation-summary').innerText");
  // Whole-request failure must not be confused with testing the rest of the family.
  await p.click('#validate-family');const failed=await next();
  await p.call('Fetch.fulfillRequest',{requestId:failed.requestId,responseCode:503,responseHeaders:[{name:'Content-Type',value:'application/json'}],body:Buffer.from(JSON.stringify({detail:'CONTROLLED HTTP failure for recovery testing'})).toString('base64')});
  await p.waitFor("document.querySelector('#status').textContent.startsWith('Run stopped')");
  const failure=await p.evaluate("({status:document.querySelector('#status').textContent,notice:document.querySelector('#notice').textContent,continueVisible:!document.querySelector('#continue-run').hidden})");
  await p.click('#validate-family');const stale=await next();await p.click('#back-editor');await p.click('.node[aria-label="Resize"]');await p.fill('#param-max_side','640');await p.click('#params-form button[type=submit]');
  try{await resume(stale);}catch{}await new Promise(r=>setTimeout(r,250));
  await p.click('#open-finish');const afterEdit=await p.evaluate("document.querySelector('#validation-summary').innerText");
  const result={tested_at:new Date().toISOString(),navigating,cancelled,completed,retryCancel,failure,afterEdit,remainingIds,checks:{navigationKeepsBatch:navigating.cancel&&navigating.status.startsWith('Running 2/5'),partialResultsKept:cancelled.summary.includes('2/5 tested'),cancelControls:cancelled.continueVisible&&!cancelled.cancelVisible,obsoleteRequestAborted:oldAborted,continuesOnlyUntested:JSON.stringify(remainingIds)===JSON.stringify(ids.slice(2)),allComplete:completed.summary.includes('5/5 tested')&&completed.continueHidden,retryCancellationKeepsPriorResults:retryCancel.includes('5/5 tested'),editRejectsOldResult:afterEdit.includes('0/5 tested'),previewSelectionKept:completed.active===ids[4],failureHonest:failure.status.includes('0/5')&&failure.status.includes('later images were not run')&&failure.continueVisible,noRuntimeErrors:errors.length===0},errors};
  await writeFile('artifacts/strict/round-08-batch.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{await p.call('Fetch.disable');p.close();}
