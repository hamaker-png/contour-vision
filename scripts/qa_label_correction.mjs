import {connect} from './cdp.mjs';
import {readFile,writeFile} from 'node:fs/promises';
const p=await connect(JSON.parse(await readFile('artifacts/strict/root-tab.json')).id);
const bodies=[],errors=[];
p.on('Fetch.requestPaused',async e=>{bodies.push(JSON.parse(e.request.postData));try{await p.call('Fetch.continueRequest',{requestId:e.requestId});}catch(error){errors.push(error.message);}});
p.on('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails.text));
try{
  await p.call('Page.bringToFront');await p.call('Runtime.enable');
  await p.call('Emulation.setDeviceMetricsOverride',{width:1424,height:905,deviceScaleFactor:1,mobile:false});
  await p.call('Fetch.enable',{patterns:[{urlPattern:'*/api/timelines/run',requestStage:'Request'}]});
  await p.call('Page.reload',{ignoreCache:true});await p.waitFor("document.querySelector('#status')?.textContent.includes('Add an image family')");
  await p.select('#examples','coins');await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");
  const original=bodies.at(-1).samples[0].boxes;
  await p.click('#to-finish');await p.click('[data-review-label]');await p.waitFor("!document.querySelector('#save-labels').disabled");
  await p.click('#label-canvas');const clickComplete=await p.evaluate("document.querySelector('#labels-complete').checked");
  await p.click('[data-label-box="6"]');await p.fill('#box-x',String(original[6].x*100+1));await p.click('#box-submit');
  const dirty=await p.evaluate("!document.querySelector('#labels-complete').checked");
  await p.click('#undo-label');const undone=await p.evaluate("({value:document.querySelector('#box-x').value,complete:document.querySelector('#labels-complete').checked})");
  await p.click('#redo-label');await p.click('#delete-label');const removed=await p.evaluate("document.querySelectorAll('[data-label-box]').length");await p.click('#undo-label');
  await p.screenshot('artifacts/strict/round-09-box-correction.png');
  await p.click('#labels-complete');await p.click('#save-labels');await p.waitFor("!document.querySelector('#label-dialog').open&&document.querySelector('#status').textContent.startsWith('Ready')");
  const submitted=bodies.at(-1).samples[0];
  const count=bodies.length;await p.click('[data-review-label]');await p.waitFor("!document.querySelector('#save-labels').disabled");await p.click('#save-labels');await new Promise(r=>setTimeout(r,250));
  const unchangedRequests=bodies.length===count;
  const validation=await p.evaluate("({rows:document.querySelectorAll('.validation-row').length,summary:document.querySelector('.validation-row').innerText,images:document.querySelectorAll('.validation-image-pair img').length,labels:document.querySelectorAll('.validation-frame rect').length,measurements:document.querySelector('.validation-measures')?.innerText})");
  await p.screenshot('artifacts/strict/round-09-validation-coins.png');
  const result={tested_at:new Date().toISOString(),checks:{plainClickKeepsComplete:clickComplete,actualEditMarksIncomplete:dirty,undoRestoresValueAndComplete:Math.abs(Number(undone.value)/100-original[6].x)<1e-8&&undone.complete,deleteOnlySelected:removed===23,saveOnlyChangesSeventh:submitted.boxes.length===24&&submitted.boxes.every((b,i)=>i===6?Math.abs(b.x-original[i].x-.01)<1e-8:JSON.stringify(b)===JSON.stringify(original[i])),completeSaved:submitted.labeled,unchangedSaveNoRun:unchangedRequests,pairedOriginalAndOutput:validation.images===2&&validation.labels===24,measurementValuesVisible:Boolean(validation.measurements?.includes('Mean RGB')),noRuntimeErrors:!errors.length},validation,errors};
  await writeFile('artifacts/strict/round-09-labels.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{await p.call('Fetch.disable');p.close();}
