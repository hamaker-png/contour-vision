// Real local CPU processing and browser downloads; no provider fixture or API key.
import assert from 'node:assert/strict';
import {newPage} from './cdp.mjs';
import {mkdir,readFile,writeFile,access} from 'node:fs/promises';
import {resolve} from 'node:path';
const directory=resolve('artifacts/expansion-browser','run-'+Date.now());
await mkdir(directory,{recursive:true});
const p=await newPage(),requests=[],errors=[];
p.on('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails.text));
p.on('Network.requestWillBeSent',e=>{
  if(e.request.url.endsWith('/api/timelines/export')&&e.request.postData)requests.push(JSON.parse(e.request.postData));
});
async function file(name){const path=resolve(directory,name);for(let i=0;i<100;i++){try{await access(path);return path;}catch{}await new Promise(r=>setTimeout(r,100));}throw Error('Download missing: '+name);}
try{
  await p.call('Page.bringToFront');await p.call('Runtime.enable');await p.call('Network.enable');
  await p.call('Emulation.setDeviceMetricsOverride',{width:1424,height:905,deviceScaleFactor:1,mobile:false});
  await p.call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:directory,eventsEnabled:true});
  await p.waitFor("document.querySelector('#examples option[value=\"candy-confirmation\"]')");
  await p.select('#examples','candy-confirmation');await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");
  await p.click('.node[data-timeline="preset1"][data-node="regions"]');
  await p.fill('#param-min_pixels','500');
  await p.click('.node[data-timeline="confirmed"][data-node="agreement"]');
  await p.click('#export-timeline');
  assert.equal(requests.length,0);
  assert.match(await p.evaluate("document.querySelector('#notice').textContent"),/pending parameters before exporting/);
  assert.equal(await p.evaluate("document.querySelector('#param-min_pixels').value"),'500');
  await p.click('[data-reset-parameters]');
  await p.click('.node[data-timeline="confirmed"][data-node="agreement"]');
  await p.click('#save');
  const saved=await file('contour-workspace.json');
  const workspace=JSON.parse(await readFile(saved,'utf8'));
  assert.equal(workspace.timelines.find(t=>t.id==='confirmed').operations[0].params.pipeline_ids,'preset1');
  await p.upload('#workspace-file',[saved]);
  await p.waitFor("document.querySelector('#status').textContent.includes('Project opened')");
  await p.click('#open-explore');await p.click('#run');await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");
  await p.click('.node[data-timeline="confirmed"][data-node="agreement"]');
  await p.click('#open-finish');
  assert.equal(await p.evaluate("document.querySelector('#export-choice').value"),'confirmed');
  await p.click('#export-chosen');await file('pipeline-detector.zip');
  assert.equal(requests.length,1);assert.equal(requests[0].selected_timeline_id,'confirmed');
  await writeFile(resolve(directory,'export-request.json'),JSON.stringify(requests[0],null,2));
  await p.screenshot(resolve(directory,'selected-confirmation-export.png'));
  assert.equal(errors.length,0);
  const result={passed:true,checked_at:new Date().toISOString(),checks:['Support draft blocks confirmation export and selects draft','Reset restores committed values','Save/open preserves support references','Reopened graph runs on CPU','Validation follows selected confirmation','Actual ZIP downloaded with selected confirmation request','No runtime exceptions'],errors,directory};
  await writeFile(resolve(directory,'report.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await p.call('Browser.setDownloadBehavior',{behavior:'default'});p.close();}
