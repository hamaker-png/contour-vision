// Real standalone Chrome: pending edits, same-ID project reopen, exact export downloads.
import {connect} from './cdp.mjs';
import {readFile,writeFile,mkdir,access} from 'node:fs/promises';
import {resolve} from 'node:path';
const p=await connect(JSON.parse(await readFile('artifacts/strict/root-tab.json')).id);
const runs=[],exports=[],downloads=[],errors=[],dest=resolve('artifacts/strict/browser-exports','run-'+Date.now());await mkdir(dest,{recursive:true});
p.on('Fetch.requestPaused',async e=>{const body=JSON.parse(e.request.postData);(e.request.url.endsWith('/export')?exports:runs).push(body);try{await p.call('Fetch.continueRequest',{requestId:e.requestId});}catch(error){errors.push(error.message);}});
p.on('Browser.downloadWillBegin',e=>downloads.push(e));p.on('Runtime.exceptionThrown',e=>errors.push(e.exceptionDetails.text));
async function file(path){for(let n=0;n<100;n++){try{await access(path);return;}catch{}await new Promise(r=>setTimeout(r,100));}throw Error('Missing download '+path);}
async function configureDownload(directory){await mkdir(directory,{recursive:true});await p.call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:directory,eventsEnabled:true});}
try{
  await p.call('Page.bringToFront');await p.call('Runtime.enable');await configureDownload(dest);
  await p.call('Emulation.setDeviceMetricsOverride',{width:1424,height:905,deviceScaleFactor:1,mobile:false});
  await p.call('Fetch.enable',{patterns:[{urlPattern:'*/api/timelines/run',requestStage:'Request'},{urlPattern:'*/api/timelines/export',requestStage:'Request'}]});
  await p.call('Page.reload',{ignoreCache:true});await p.waitFor("document.querySelector('#status')?.textContent.includes('Add an image family')");
  await p.select('#examples','red-candies');await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");
  await p.click('.node[aria-label="Resize"]');await p.click('#save');await file(resolve(dest,'contour-workspace.json'));
  const downloadCount=downloads.length;
  await p.fill('#param-max_side','640');await p.click('#close-inspector');await p.click('.node[aria-label="Gaussian blur"]');await p.click('#close-inspector');await p.click('.node[aria-label="Resize"]');
  const retained=await p.evaluate("({value:document.querySelector('#param-max_side').value,pending:!document.querySelector('#pending-parameters').hidden})");
  await p.click('#save');await new Promise(r=>setTimeout(r,100));
  const saveBlocked=downloads.length===downloadCount&&await p.evaluate("document.querySelector('#notice').textContent.includes('Apply or reset')");
  await p.click('#export-timeline');const exportBlocked=exports.length===0&&await p.evaluate("document.querySelector('#notice').textContent.includes('before exporting')");
  await p.upload('#workspace-file',[resolve(dest,'contour-workspace.json')]);await p.waitFor("document.querySelector('#pending-parameters').hidden&&document.querySelector('#param-max_side')?.value==='1280'");
  const reopened=await p.evaluate("({value:document.querySelector('#param-max_side').value,pending:!document.querySelector('#pending-parameters').hidden})");
  // A committed name edit is independent of Resize; undo must not retain a stale raw form.
  await p.fill('#timeline-name','Renamed for history check');await p.click('#param-max_side');await p.fill('#param-max_side','700');await p.click('#undo');
  const undone=await p.evaluate("({value:document.querySelector('#param-max_side')?.value,pending:!document.querySelector('#pending-parameters').hidden})");
  await p.fill('#param-max_side','640');await p.click('#params-form button[type=submit]');await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");
  const latest=runs.at(-1);const applyCorrect=latest.timelines.flatMap(t=>t.operations).find(o=>o.kind==='resize').params.max_side===640;
  await p.click('#edit-brief');await p.click('.target-brief details summary');await p.fill('#scale','2');await p.click('#unit');await p.click('#open-finish');
  await p.click('#validate-family');await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");
  const photo=resolve(dest,'photo');await configureDownload(photo);await p.click('#export-chosen');await file(resolve(photo,'timeline-detector.zip'));
  await writeFile(resolve(photo,'expected-workspace.json'),JSON.stringify(runs.at(-1),null,2));await writeFile(resolve(photo,'export-request.json'),JSON.stringify(exports.at(-1),null,2));
  const photoUI=await p.evaluate("({summary:document.querySelector('.validation-row').innerText,measurements:document.querySelector('.validation-measures').innerText})");
  await p.click('#toggle-images');await p.select('#examples','green-shapes');await p.waitFor("document.querySelector('#status').textContent.startsWith('Ready')");await p.click('#to-finish');
  const twoD=resolve(dest,'2d');await configureDownload(twoD);await p.click('#export-chosen');await file(resolve(twoD,'timeline-detector.zip'));
  await writeFile(resolve(twoD,'expected-workspace.json'),JSON.stringify(runs.at(-1),null,2));await writeFile(resolve(twoD,'export-request.json'),JSON.stringify(exports.at(-1),null,2));
  const twoDUI=await p.evaluate("({summary:document.querySelector('.validation-row').innerText,measurements:document.querySelector('.validation-measures').innerText})");
  await p.screenshot('artifacts/strict/round-10-export-2d.png');
  const result={tested_at:new Date().toISOString(),exportDirs:{photo,twoD},retained,reopened,undone,photoUI,twoDUI,checks:{rawDraftSurvivesSelection:retained.value==='640'&&retained.pending,saveBlocksUnapplied:saveBlocked,exportBlocksUnapplied:exportBlocked,sameIdOpenResetsVisibleForm:reopened.value==='1280'&&!reopened.pending,undoResetsVisibleForm:undone.value==='1280'&&!undone.pending,appliedValueSent:applyCorrect,photoMeasurementsInUnits:photoUI.measurements.includes(' mm'),twoDMeasurementsVisible:twoDUI.measurements.includes('Length:'),newExampleResetsPhysicalScale:twoDUI.measurements.includes(' px'),twoRealDownloads:exports.length===2,noRuntimeErrors:errors.length===0},errors};
  await writeFile('artifacts/strict/round-10-export.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{await p.call('Fetch.disable');p.close();}
